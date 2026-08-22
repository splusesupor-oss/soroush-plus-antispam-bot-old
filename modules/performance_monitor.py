"""Non-blocking owner-only monitoring for slow message handlers.

Crash delivery remains in ``watchdog_reporting.py``.  This module handles only
live-process performance events and never writes to the crash queue.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from modules.owner_private import resolve_private_owner_peer
from modules.runtime_paths import runtime_config_file
from modules.time_utils import now_local


STATE_FILE = runtime_config_file("performance_monitor_state.json", migrate=False)
MIN_THRESHOLD_MS = 150.0
DEFAULT_COOLDOWN_SECONDS = 10 * 60.0
DEFAULT_GLOBAL_MIN_INTERVAL_SECONDS = 5 * 60.0
# Owner delivery is intentionally much stricter than local slow-event logs.
# A 150ms event is useful diagnostics, but it must never create an RPC.
DEFAULT_OWNER_NOTIFY_THRESHOLD_MS = 2000.0
DEFAULT_RPC_PRESSURE_LIMIT = 8
DEFAULT_QUEUE_SIZE = 8
_STATE_RETENTION_SECONDS = 24 * 60 * 60


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, float(default))


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, int(default))


def _safe_handler(value: Any) -> str:
    text = "_".join(str(value or "unknown_handler").strip().split())
    return text[:120] or "unknown_handler"


def _message_id(event: Any) -> Any:
    message = getattr(event, "message", None)
    return getattr(message, "id", None) if message is not None else None


def _atomic_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            try:
                os.fsync(stream.fileno())
            except OSError:
                pass
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _load_state(path: Path, now: Optional[float] = None) -> Dict[str, Any]:
    timestamp = time.time() if now is None else float(now)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    raw_last = data.get("last_report", {})
    last_report: Dict[str, float] = {}
    if isinstance(raw_last, dict):
        for key, value in raw_last.items():
            try:
                recorded = float(value)
            except (TypeError, ValueError):
                continue
            if timestamp - recorded <= _STATE_RETENTION_SECONDS:
                last_report[str(key)] = recorded
    try:
        last_global = float(data.get("last_global", 0.0))
    except (TypeError, ValueError):
        last_global = 0.0
    if timestamp - last_global > _STATE_RETENTION_SECONDS:
        last_global = 0.0
    return {
        "version": 1,
        "last_report": last_report,
        "last_global": last_global,
    }


class SlowProcessMonitor:
    """Record every >150ms handler and privately notify the owner in background."""

    def __init__(
        self,
        client: Any,
        logger: Any,
        *,
        cooldown_seconds: Optional[float] = None,
        global_min_interval_seconds: Optional[float] = None,
        owner_notify_threshold_ms: Optional[float] = None,
        rpc_pressure_limit: Optional[int] = None,
        queue_size: Optional[int] = None,
        state_path: Optional[os.PathLike] = None,
        send_timeout: float = 60.0,
    ):
        # Product rule: every handler above 150ms is slow, and values at or
        # below 150ms must never notify the owner.  Keep this boundary fixed so
        # deployment configuration cannot accidentally weaken the guarantee.
        self.threshold_ms = MIN_THRESHOLD_MS
        self.cooldown_seconds = (
            _env_float(
                "WATCHDOG_SLOW_COOLDOWN_SECONDS",
                DEFAULT_COOLDOWN_SECONDS,
            )
            if cooldown_seconds is None else max(0.0, float(cooldown_seconds))
        )
        self.global_min_interval_seconds = (
            _env_float(
                "WATCHDOG_SLOW_GLOBAL_MIN_INTERVAL_SECONDS",
                DEFAULT_GLOBAL_MIN_INTERVAL_SECONDS,
            )
            if global_min_interval_seconds is None
            else max(0.0, float(global_min_interval_seconds))
        )
        self.owner_notify_threshold_ms = (
            _env_float(
                "WATCHDOG_SLOW_OWNER_NOTIFY_THRESHOLD_MS",
                DEFAULT_OWNER_NOTIFY_THRESHOLD_MS,
                minimum=MIN_THRESHOLD_MS,
            )
            if owner_notify_threshold_ms is None
            else max(MIN_THRESHOLD_MS, float(owner_notify_threshold_ms))
        )
        self.rpc_pressure_limit = (
            _env_int("WATCHDOG_SLOW_RPC_PRESSURE_LIMIT", DEFAULT_RPC_PRESSURE_LIMIT)
            if rpc_pressure_limit is None
            else max(1, int(rpc_pressure_limit))
        )
        selected_queue_size = (
            _env_int("WATCHDOG_SLOW_QUEUE_SIZE", DEFAULT_QUEUE_SIZE)
            if queue_size is None else max(1, int(queue_size))
        )
        self.client = client
        self.logger = logger
        self.state_path = Path(state_path) if state_path is not None else STATE_FILE
        self.send_timeout = max(1.0, float(send_timeout))
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=selected_queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._closed = False
        self._pending = set()
        self._suppressed: Dict[str, int] = {}
        state = _load_state(self.state_path)
        self._last_report: Dict[str, float] = state["last_report"]
        self._last_global = float(state["last_global"])

    def _log_info(self, message: str) -> None:
        method = getattr(self.logger, "log_info", None)
        if callable(method):
            method(message)

    def _log_error(self, message: str) -> None:
        method = getattr(self.logger, "log_error", None)
        if callable(method):
            method(message)

    def start(self) -> bool:
        if self._closed:
            return False
        if self._worker_task is not None and not self._worker_task.done():
            return True
        self._worker_task = asyncio.create_task(
            self._worker(), name="slow-process-owner-reporter"
        )
        self._log_info(
            "SLOW PROCESS MONITOR STARTED "
            f"threshold_ms={self.threshold_ms:.1f} "
            f"cooldown_s={self.cooldown_seconds:.1f} "
            f"global_min_interval_s={self.global_min_interval_seconds:.1f} "
            f"owner_notify_threshold_ms={self.owner_notify_threshold_ms:.1f} "
            f"rpc_pressure_limit={self.rpc_pressure_limit}"
        )
        return True

    def update_client(self, client: Any) -> None:
        self.client = client

    def _dedup_key(self, handler: str, chat_id: Any) -> str:
        raw = f"{handler}|{chat_id}"
        return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()

    def record(
        self,
        *,
        total_ms: float,
        chat_id: Any,
        message_id: Any,
        handler: str,
        timestamp: Optional[str] = None,
        now_epoch: Optional[float] = None,
    ) -> bool:
        """Log a slow event and enqueue at most one deduplicated owner report.

        This method performs no await and no disk/network I/O.  It is safe to
        call from the message hot path.
        """
        try:
            elapsed = float(total_ms)
        except (TypeError, ValueError):
            return False
        if elapsed <= self.threshold_ms:
            return False

        handler_name = _safe_handler(handler)
        event_timestamp = timestamp or now_local().isoformat()
        line = (
            "SLOW_PROCESS "
            f"total_ms={elapsed:.1f} "
            f"chat_id={chat_id} "
            f"message_id={message_id} "
            f"handler={handler_name} "
            f"timestamp={event_timestamp}"
        )
        # Every slow event is retained locally, even when owner delivery is
        # suppressed by cooldown.
        self._log_info(line)

        # Local logging is cheap and intentionally covers every >150ms event.
        # Private reports are diagnostics only, so never turn routine latency
        # into another competing send_message RPC.
        if elapsed < self.owner_notify_threshold_ms:
            return False

        if self._closed:
            return False
        if self._worker_task is None or self._worker_task.done():
            try:
                self.start()
            except RuntimeError as error:
                self._log_error(f"SLOW_PROCESS MONITOR START FAILED error={error!r}")
                return False

        now = time.time() if now_epoch is None else float(now_epoch)
        key = self._dedup_key(handler_name, chat_id)
        last_for_key = float(self._last_report.get(key, 0.0))
        if key in self._pending or now - last_for_key < self.cooldown_seconds:
            self._suppressed[key] = int(self._suppressed.get(key, 0)) + 1
            return False
        if now - self._last_global < self.global_min_interval_seconds:
            self._suppressed[key] = int(self._suppressed.get(key, 0)) + 1
            return False

        event = {
            "type": "SLOW_PROCESS",
            "total_ms": round(elapsed, 3),
            "chat_id": chat_id,
            "message_id": message_id,
            "handler": handler_name,
            "timestamp": event_timestamp,
            "key": key,
            "suppressed": int(self._suppressed.pop(key, 0)),
        }
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self._log_error(
                "SLOW_PROCESS OWNER QUEUE FULL "
                f"handler={handler_name} chat_id={chat_id}"
            )
            return False
        self._pending.add(key)
        # Reserve cooldown before network I/O.  A broken connection therefore
        # cannot create a task/report storm on every incoming message.
        self._last_report[key] = now
        self._last_global = now
        return True

    @staticmethod
    def _size_of(value: Any) -> int:
        try:
            return len(value)
        except (TypeError, AttributeError):
            return 0

    def _rpc_pressure(self) -> int:
        """Best-effort count of pending transport requests; no RPC is made."""
        sender = getattr(self.client, "_sender", None)
        if sender is None:
            return 0
        return max(
            self._size_of(getattr(sender, "_pending_state", None)),
            self._size_of(getattr(sender, "_pending", None)),
            self._size_of(getattr(sender, "_send_queue", None)),
        )

    async def _private_owner_target(self) -> Any:
        return await resolve_private_owner_peer(
            self.client,
            logger=self.logger,
            context="SLOW_PROCESS",
        )

    @staticmethod
    def format_report(event: Dict[str, Any]) -> str:
        summary = (
            "SLOW_PROCESS "
            f"total_ms={float(event['total_ms']):.1f} "
            f"chat_id={event.get('chat_id')} "
            f"message_id={event.get('message_id')} "
            f"handler={event.get('handler')} "
            f"timestamp={event.get('timestamp')}"
        )
        suppressed = int(event.get("suppressed", 0) or 0)
        if suppressed:
            summary += f"\nsuppressed_since_last={suppressed}"
        return (
            "⚠️ گزارش کندی ربات\n\n"
            "نوع: SLOW_PROCESS\n"
            f"زمان کل پردازش: {float(event['total_ms']):.1f} ms\n"
            f"chat_id: {event.get('chat_id')}\n"
            f"message_id: {event.get('message_id')}\n"
            f"handler: {event.get('handler')}\n"
            f"timestamp: {event.get('timestamp')}\n\n"
            f"{summary}"
        )

    def _state_payload(self) -> Dict[str, Any]:
        cutoff = time.time() - _STATE_RETENTION_SECONDS
        self._last_report = {
            key: value
            for key, value in self._last_report.items()
            if value >= cutoff
        }
        return {
            "version": 1,
            "last_report": dict(self._last_report),
            "last_global": self._last_global,
        }

    async def _persist_state(self) -> None:
        payload = self._state_payload()
        try:
            await asyncio.to_thread(_atomic_json_write, self.state_path, payload)
        except Exception as error:
            self._log_error(
                f"SLOW_PROCESS STATE WRITE FAILED error={error!r}"
            )

    async def _worker(self) -> None:
        while True:
            event = await self.queue.get()
            key = event["key"]
            try:
                pressure = self._rpc_pressure()
                if pressure >= self.rpc_pressure_limit:
                    self._log_info(
                        "SLOW_PROCESS OWNER REPORT SKIPPED RPC_PRESSURE "
                        f"handler={event['handler']} chat_id={event['chat_id']} "
                        f"pending_rpc={pressure} limit={self.rpc_pressure_limit}"
                    )
                    continue
                target = await self._private_owner_target()
                result = self.client.send_message(target, self.format_report(event))
                if inspect.isawaitable(result):
                    await asyncio.wait_for(result, timeout=self.send_timeout)
                self._log_info(
                    "SLOW_PROCESS OWNER REPORT SENT "
                    f"handler={event['handler']} chat_id={event['chat_id']} "
                    f"message_id={event['message_id']}"
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._log_error(
                    "SLOW_PROCESS OWNER REPORT FAILED "
                    f"handler={event['handler']} chat_id={event['chat_id']} "
                    f"error={error!r}"
                )
            finally:
                self._pending.discard(key)
                # Persist before task_done so queue.join() also guarantees the
                # cross-restart cooldown state reached disk.
                await self._persist_state()
                self.queue.task_done()

    async def close(self) -> None:
        self._closed = True
        task = self._worker_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._worker_task = None
