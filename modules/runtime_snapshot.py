"""دوره‌ای، فقط خواندنی: علت کند شدن تدریجی ربات را در لاگ مشخص می‌کند.

هیچ صف، Governor، concurrency یا cache ای را تغییر نمی‌دهد. فقط متریک
می‌خواند، با مقدار قبلی مقایسه می‌کند و رشد/انباشت را لاگ می‌کند.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, Optional


METRIC_KEYS = (
    "event_loop_lag_ms",
    "pending_tasks",
    "active_tasks",
    "moderation_queue_pending",
    "delete_queue_pending",
    "normal_queue_pending",
    "rpc_pending",
    "rpc_governor_wait_ms",
    "sender_pending",
    "active_auto_notice_timers",
    "username_directory_cache_size",
    "economy_cache_size",
    "peer_cache_size",
    "memory_mb",
)

# Size-like metrics: a rising value over time is the signal we want.
GROWTH_METRICS = (
    "pending_tasks",
    "active_tasks",
    "moderation_queue_pending",
    "delete_queue_pending",
    "normal_queue_pending",
    "rpc_pending",
    "rpc_governor_wait_ms",
    "sender_pending",
    "active_auto_notice_timers",
    "username_directory_cache_size",
    "economy_cache_size",
    "peer_cache_size",
    "memory_mb",
)

QUEUE_METRICS = (
    "moderation_queue_pending",
    "delete_queue_pending",
    "normal_queue_pending",
)

CACHE_METRICS = (
    "username_directory_cache_size",
    "economy_cache_size",
    "peer_cache_size",
)

MILESTONES_SECONDS = (30 * 60, 60 * 60, 90 * 60)

DEFAULT_INTERVAL_SECONDS = 45.0
LAG_PROBE_SECONDS = 0.05
LAG_WARN_MS = 50.0
TASK_GROWTH_DELTA = 20
TASK_GROWTH_ABS = 150
QUEUE_BACKLOG = 5
RPC_BACKLOG = 10
NOTICE_GROWTH_DELTA = 5
CACHE_GROWTH_DELTA = 10
MEMORY_GROWTH_MB = 8.0


def _safe_len(value: Any) -> int:
    try:
        return len(value)
    except (TypeError, AttributeError):
        return 0


def _qsize_sum(queues: Any) -> int:
    total = 0
    try:
        values = queues.values() if hasattr(queues, "values") else queues
    except Exception:
        return 0
    for queue in values or ():
        try:
            total += int(queue.qsize())
        except Exception:
            continue
    return total


def _rss_mb() -> float:
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS"):
                    return float(line.split()[1]) / 1024.0
    except OSError:
        pass
    try:
        import resource
        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    except Exception:
        return 0.0


def _task_counts() -> tuple[int, int]:
    try:
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
    except Exception:
        return 0, 0
    active = len(tasks)
    current = asyncio.current_task()
    pending = sum(1 for task in tasks if task is not current)
    return pending, active


async def _event_loop_lag_ms(probe_seconds: float = LAG_PROBE_SECONDS) -> float:
    expected = max(0.0, float(probe_seconds))
    started = time.perf_counter()
    await asyncio.sleep(expected)
    return max(0.0, (time.perf_counter() - started - expected) * 1000.0)


def _governor_wait_ms(governor: Any) -> float:
    if governor is None:
        return 0.0
    now = time.perf_counter()
    longest = 0.0
    try:
        for groups in getattr(governor, "_queues", {}).values():
            for waiters in groups.values():
                for waiter in waiters:
                    future = getattr(waiter, "future", None)
                    if future is not None and getattr(future, "done", lambda: True)():
                        continue
                    enqueued = float(getattr(waiter, "enqueued_at", now) or now)
                    longest = max(longest, (now - enqueued) * 1000.0)
    except Exception:
        return 0.0
    return longest


def _username_directory_size() -> int:
    try:
        from economy import storage
        cache = getattr(storage, "_cache", None)
        if not isinstance(cache, dict):
            return 0
        books = cache.get("usernames") or {}
        if not isinstance(books, dict):
            return 0
        return sum(len(book) if isinstance(book, dict) else 1 for book in books.values())
    except Exception:
        return 0


def _economy_cache_size() -> int:
    try:
        from economy import storage
        cache = getattr(storage, "_cache", None)
        if not isinstance(cache, dict):
            return 0
        users = cache.get("users") or {}
        return len(users) if isinstance(users, dict) else 0
    except Exception:
        return 0


def _notice_timer_count(bot: Any) -> int:
    notice = getattr(bot, "notice_cleanup", None)
    if notice is None:
        return 0
    items = getattr(notice, "_items", {}) or {}
    try:
        return sum(len(rows) for rows in items.values())
    except Exception:
        return _safe_len(items)


def _normal_queue_pending(bot: Any) -> int:
    dispatcher = getattr(bot, "group_dispatcher", None)
    if dispatcher is None:
        return 0
    pending_map = getattr(dispatcher, "_normal_pending", None) or {}
    mapped = 0
    try:
        mapped = sum(int(value) for value in pending_map.values())
    except Exception:
        mapped = 0
    queued = 0
    try:
        from modules.group_dispatch import LANE_NORMAL
        for (chat, lane), queue in getattr(dispatcher, "_queues", {}).items():
            if lane == LANE_NORMAL:
                queued += int(queue.qsize())
    except Exception:
        queued = 0
    return max(mapped, queued)


def collect_sync(bot: Any) -> Dict[str, Any]:
    """Cheap, non-awaiting counters. Loop lag is filled in by collect()."""
    started_at = float(getattr(bot, "started_at", time.time()) or time.time())
    uptime = max(0, int(time.time() - started_at))

    pending_tasks, active_tasks = _task_counts()

    moderation = getattr(bot, "moderation_queue", None)
    moderation_pending = _safe_len(getattr(moderation, "_pending_keys", None))
    if moderation_pending == 0 and moderation is not None:
        moderation_pending = _qsize_sum(getattr(moderation, "_queues", {}))

    delete_queue = getattr(bot, "message_delete_queue", None)
    delete_pending = _qsize_sum(getattr(delete_queue, "_queues", {}) if delete_queue else {})
    if delete_pending == 0 and delete_queue is not None:
        delete_pending = _safe_len(getattr(delete_queue, "_pending_ids", None))

    rpc_pending = 0
    sender_pending = 0
    try:
        from modules.outgoing_profiler import pending_rpc_snapshot
        sender = getattr(getattr(bot, "client", None), "_sender", None)
        snap = pending_rpc_snapshot(sender)
        rpc_pending = int(snap.get("count") or 0)
        sender_pending = int(snap.get("sender_pending") or 0)
    except Exception:
        pass
    outgoing = getattr(bot, "outgoing_sender", None)
    if outgoing is not None:
        try:
            sender_pending = max(sender_pending, int(outgoing._normal_pending()))
        except Exception:
            try:
                sender_pending = max(sender_pending, _qsize_sum(getattr(outgoing, "_queues", {})))
            except Exception:
                pass

    governor = getattr(bot, "rpc_governor", None)
    governor_wait_ms = _governor_wait_ms(governor)

    peer_cache = getattr(bot, "reply_input_peer_cache", None) or {}

    return {
        "uptime": uptime,
        "event_loop_lag_ms": 0.0,
        "pending_tasks": int(pending_tasks),
        "active_tasks": int(active_tasks),
        "moderation_queue_pending": int(moderation_pending),
        "delete_queue_pending": int(delete_pending),
        "normal_queue_pending": int(_normal_queue_pending(bot)),
        "rpc_pending": int(rpc_pending),
        "rpc_governor_wait_ms": round(float(governor_wait_ms), 1),
        "sender_pending": int(sender_pending),
        "active_auto_notice_timers": int(_notice_timer_count(bot)),
        "username_directory_cache_size": int(_username_directory_size()),
        "economy_cache_size": int(_economy_cache_size()),
        "peer_cache_size": int(_safe_len(peer_cache)),
        "memory_mb": round(_rss_mb(), 1),
    }


async def collect(bot: Any, *, lag_probe_seconds: float = LAG_PROBE_SECONDS) -> Dict[str, Any]:
    snapshot = collect_sync(bot)
    snapshot["event_loop_lag_ms"] = round(await _event_loop_lag_ms(lag_probe_seconds), 1)
    pending_tasks, active_tasks = _task_counts()
    snapshot["pending_tasks"] = int(pending_tasks)
    snapshot["active_tasks"] = int(active_tasks)
    return snapshot


def format_snapshot(snapshot: Dict[str, Any], *, title: str = "PERFORMANCE SNAPSHOT") -> str:
    lines = [title, f"uptime={int(snapshot.get('uptime', 0))}s"]
    for key in METRIC_KEYS:
        value = snapshot.get(key, 0)
        if isinstance(value, float):
            lines.append(f"{key}={value:.1f}" if key.endswith("_ms") or key == "memory_mb" else f"{key}={value}")
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines)


def detect_issues(current: Dict[str, Any], previous: Optional[Dict[str, Any]] = None) -> list[str]:
    """Compare snapshots. Never mutates bot state."""
    lines: list[str] = []
    lag = float(current.get("event_loop_lag_ms") or 0.0)
    if lag >= LAG_WARN_MS:
        lines.append(f"EVENT LOOP LAG DETECTED lag_ms={lag:.1f}")

    active = int(current.get("active_tasks") or 0)
    pending = int(current.get("pending_tasks") or 0)
    prev_active = int((previous or {}).get("active_tasks") or 0)
    if active >= TASK_GROWTH_ABS or (previous and active - prev_active >= TASK_GROWTH_DELTA):
        lines.append(f"TASK GROWTH DETECTED active={active} pending={pending}")

    for queue_name in QUEUE_METRICS:
        value = int(current.get(queue_name) or 0)
        if value >= QUEUE_BACKLOG:
            lines.append(f"QUEUE BACKLOG DETECTED queue={queue_name} pending={value}")

    rpc_pending = int(current.get("rpc_pending") or 0)
    sender_pending = int(current.get("sender_pending") or 0)
    if rpc_pending >= RPC_BACKLOG or sender_pending >= RPC_BACKLOG:
        lines.append(
            f"RPC BACKLOG DETECTED pending={rpc_pending} sender_pending={sender_pending}"
        )

    notices = int(current.get("active_auto_notice_timers") or 0)
    prev_notices = int((previous or {}).get("active_auto_notice_timers") or 0)
    if notices >= NOTICE_GROWTH_DELTA and (previous is None or notices > prev_notices):
        lines.append(f"AUTO NOTICE TIMER GROWTH DETECTED active={notices}")

    for cache_name in CACHE_METRICS:
        size = int(current.get(cache_name) or 0)
        prev = int((previous or {}).get(cache_name) or 0)
        if size - prev >= CACHE_GROWTH_DELTA or (previous is None and size >= CACHE_GROWTH_DELTA * 5):
            lines.append(f"CACHE GROWTH DETECTED cache={cache_name} size={size}")

    if previous:
        for metric in GROWTH_METRICS:
            before = previous.get(metric, 0)
            after = current.get(metric, 0)
            try:
                delta = float(after) - float(before)
            except (TypeError, ValueError):
                continue
            if metric == "memory_mb":
                if delta < MEMORY_GROWTH_MB:
                    continue
            elif metric.endswith("_ms"):
                if delta < LAG_WARN_MS:
                    continue
            elif delta <= 0:
                continue
            lines.append(
                f"GROWING STATE DETECTED metric={metric} "
                f"previous={before} current={after} delta={delta if metric == 'memory_mb' or metric.endswith('_ms') else int(delta)}"
            )
    return lines


def vs_baseline_lines(current: Dict[str, Any], baseline: Dict[str, Any]) -> list[str]:
    lines = ["PERFORMANCE VS BASELINE"]
    unusual = []
    for key in METRIC_KEYS:
        before = baseline.get(key, 0)
        after = current.get(key, 0)
        try:
            delta = float(after) - float(before)
        except (TypeError, ValueError):
            continue
        lines.append(f"{key} baseline={before} current={after} delta={delta:.1f}")
        grown = False
        if key == "memory_mb":
            grown = delta >= MEMORY_GROWTH_MB * 2
        elif key == "event_loop_lag_ms":
            grown = float(after) >= LAG_WARN_MS * 2
        elif key in QUEUE_METRICS or key in ("rpc_pending", "sender_pending"):
            grown = float(after) >= QUEUE_BACKLOG
        elif key in CACHE_METRICS or key in ("active_tasks", "pending_tasks", "active_auto_notice_timers"):
            grown = delta >= max(CACHE_GROWTH_DELTA, float(before) * 0.5 if float(before) else CACHE_GROWTH_DELTA)
        if grown:
            unusual.append(key)
    if unusual:
        lines.append("UNUSUAL GROWTH SINCE START metrics=" + ",".join(unusual))
    else:
        lines.append("UNUSUAL GROWTH SINCE START metrics=none")
    return lines


class RuntimeSnapshotMonitor:
    """Background loop: baseline at t=0, then every 30–60s."""

    def __init__(
        self,
        bot: Any,
        logger: Any,
        *,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        lag_probe_seconds: float = LAG_PROBE_SECONDS,
    ):
        self.bot = bot
        self.logger = logger
        env_interval = os.environ.get("BOT_RUNTIME_SNAPSHOT_SECONDS", "").strip()
        if env_interval:
            try:
                interval_seconds = float(env_interval)
            except ValueError:
                pass
        self.interval_seconds = min(60.0, max(30.0, float(interval_seconds))) if interval_seconds >= 1 else max(0.01, float(interval_seconds))
        self.lag_probe_seconds = max(0.0, float(lag_probe_seconds))
        self._task: Optional[asyncio.Task] = None
        self._closed = False
        self.previous: Optional[Dict[str, Any]] = None
        self.baseline: Optional[Dict[str, Any]] = None
        self._milestones_logged = set()
        self.snapshots: list[Dict[str, Any]] = []

    def _log(self, message: str, *, error: bool = False) -> None:
        if self.logger is None:
            return
        method = getattr(self.logger, "log_error" if error else "log_info", None)
        if callable(method):
            method(message)

    async def emit(self, *, title: str = "PERFORMANCE SNAPSHOT") -> Dict[str, Any]:
        snapshot = await collect(self.bot, lag_probe_seconds=self.lag_probe_seconds)
        self._log(format_snapshot(snapshot, title=title))
        for line in detect_issues(snapshot, self.previous):
            self._log(line, error=True)
        if self.baseline is None:
            self.baseline = dict(snapshot)
            self._log("PERFORMANCE BASELINE RECORDED")
        uptime = int(snapshot.get("uptime") or 0)
        for mark in MILESTONES_SECONDS:
            if uptime >= mark and mark not in self._milestones_logged:
                self._milestones_logged.add(mark)
                self._log(f"PERFORMANCE MILESTONE elapsed={mark}s")
                for line in vs_baseline_lines(snapshot, self.baseline):
                    self._log(line)
        self.previous = dict(snapshot)
        self.snapshots.append(snapshot)
        if len(self.snapshots) > 200:
            self.snapshots = self.snapshots[-100:]
        return snapshot

    async def _run_loop(self) -> None:
        try:
            await self.emit(title="PERFORMANCE SNAPSHOT")
            while not self._closed:
                await asyncio.sleep(self.interval_seconds)
                if self._closed:
                    break
                await self.emit(title="PERFORMANCE SNAPSHOT")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._log(f"RUNTIME SNAPSHOT LOOP FAILED error={error!r}", error=True)

    def start(self) -> bool:
        if self._closed:
            return False
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run_loop(), name="runtime-performance-snapshot"
            )
        return True

    async def stop(self) -> None:
        self._closed = True
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None
