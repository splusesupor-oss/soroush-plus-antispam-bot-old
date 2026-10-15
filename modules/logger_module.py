"""Bounded, non-blocking operational and moderation-audit logging.

Producers only enqueue small records. Formatting, JSON encoding, console and
rotating-file I/O run on listeners, never on the message/RPC worker.
"""
from __future__ import annotations

import atexit
import copy
import json
import logging
import os
import queue
import sys
from datetime import datetime
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Optional

from modules.runtime_paths import runtime_log_file
from modules.log_policy import VERBOSE as _VERBOSE, NOISY_PREFIXES as _NOISY_PREFIXES, important_info


def _env_int(name, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(os.environ.get(name, default))))
    except (ValueError, TypeError):
        return default


_MAX_LOG_BYTES = _env_int("BOT_LOG_MAX_BYTES", 3 * 1024 * 1024, 1024 * 1024, 1024 * 1024 * 1024)
_LOG_BACKUPS = _env_int("BOT_LOG_BACKUPS", 2, 1, 20)
_TEXT_LIMIT = _env_int("BOT_LOG_TEXT_LIMIT", 160, 0, 500)


class _DroppingQueueHandler(QueueHandler):
    """Do not format or wait for storage when called from the event loop."""
    dropped = 0

    def prepare(self, record):
        # Unlike QueueHandler.prepare(), do not eagerly format strings/JSON.
        # Records stay in this process; args are immutable scalars at our API.
        return copy.copy(record)

    def enqueue(self, record):
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            type(self).dropped += 1
            self.queue.bot_dropped = getattr(self.queue, "bot_dropped", 0) + 1


class _AuditFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            # RotatingFileHandler formats once to check size and again to emit.
            # Cache on the listener-owned record, not on the producer's payload.
            cached = getattr(record, "bot_audit_json", None)
            if cached is None:
                entry = dict(record.msg)
                entry["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
                cached = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
                record.bot_audit_json = cached
            return cached
        return super().format(record)


class _ReportingQueueListener(QueueListener):
    """Surface audit/log loss rather than silently dropping under pressure."""
    def __init__(self, q, *handlers):
        super().__init__(q, *handlers, respect_handler_level=True)
        self._reported_drops = 0

    def _report_drops(self):
        total = getattr(self.queue, "bot_dropped", 0)
        if total == self._reported_drops:
            return
        # Report once per drain/shutdown, not once for each lost record.
        record = logging.LogRecord("SoroushAntiSpam", logging.WARNING, "", 0,
            {"event": "LOG_QUEUE_OVERFLOW", "dropped": total - self._reported_drops,
             "total_dropped": total}, (), None)
        for handler in self.handlers:
            handler.handle(record)
        self._reported_drops = total

    def handle(self, record):
        super().handle(record)
        if self.queue.empty():
            self._report_drops()

    def enqueue_sentinel(self):
        # Blocking is allowed ONLY during explicit shutdown, not in producers.
        # QueueListener's put_nowait sentinel can otherwise fail on a full queue.
        self.queue.put(self._sentinel)

    def stop(self):
        if self._thread is not None:
            super().stop()
            self._report_drops()


def _rotating_handler(filename, *, audit=False):
    path = runtime_log_file(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=_MAX_LOG_BYTES,
        backupCount=_LOG_BACKUPS, encoding="utf-8")
    handler.setFormatter(_AuditFormatter("%(message)s") if audit else
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    return handler


class _LogRuntime:
    def __init__(self):
        # Preserve both existing capacities; actions share the audit listener.
        self.queue = queue.Queue(maxsize=10_000)
        self.deleted_queue = queue.Queue(maxsize=10_000)
        console = logging.StreamHandler()
        console.addFilter(lambda r: not getattr(r, "bot_no_console", False))
        console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        self.file_handler = _rotating_handler("bot.log")
        self.deleted_handler = _rotating_handler("deleted_messages.log", audit=True)
        self.actions_handler = _rotating_handler("actions.log", audit=True)
        self.deleted_handler.addFilter(lambda r: r.name.endswith(".deleted") or r.levelno >= logging.WARNING)
        self.actions_handler.addFilter(lambda r: r.name.endswith(".actions") or r.levelno >= logging.WARNING)
        self.handlers = (console, self.file_handler, self.deleted_handler, self.actions_handler)
        self.listener = _ReportingQueueListener(self.queue, console, self.file_handler)
        self.deleted_listener = _ReportingQueueListener(self.deleted_queue, self.deleted_handler, self.actions_handler)
        self.listener.start()
        self.deleted_listener.start()
        self._closed = False

    def stop(self):
        if self._closed:
            return
        self._closed = True
        for listener in (self.listener, self.deleted_listener):
            try:
                listener.stop()
            except Exception as error:
                sys.stderr.write(f"LOG SHUTDOWN FAILED: {error!r}\n")
        for handler in self.handlers:
            handler.close()


_RUNTIME = None
_RUNTIME_LOCK = Lock()


def _runtime():
    global _RUNTIME
    if _RUNTIME is None:
        with _RUNTIME_LOCK:
            if _RUNTIME is None:
                _RUNTIME = _LogRuntime()
                atexit.register(_RUNTIME.stop)
    return _RUNTIME


def _queued_logger(name, target):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(isinstance(h, _DroppingQueueHandler) and h.queue is target for h in logger.handlers):
        logger.handlers.clear()
        logger.addHandler(_DroppingQueueHandler(target))
    return logger


class BotLogger:
    def __init__(self, log_file: str = "logs/deleted_messages.log", console_log: bool = True):
        # Retain the existing API and central runtime paths.
        self.log_file = str(runtime_log_file(Path(log_file).name))
        self.verbose_logs = _VERBOSE
        self._extra = {"bot_no_console": not console_log}
        runtime = _runtime()
        self.logger = _queued_logger("SoroushAntiSpam", runtime.queue)
        self._deleted_logger = _queued_logger("SoroushAntiSpam.deleted", runtime.deleted_queue)
        self._actions_logger = _queued_logger("SoroushAntiSpam.actions", runtime.deleted_queue)

    def log_deleted_message(self, user_id: int, username: Optional[str], group_id: int,
                            group_title: Optional[str], original_text: str, reason: str,
                            message_id: Optional[int] = None):
        # IDs/reason/time remain intact. Do not stringify or encode the full text.
        entry = {"user_id": user_id, "username": username, "group_id": group_id,
            "group_title": group_title, "message_id": message_id,
            "original_text": (original_text or "")[:_TEXT_LIMIT], "reason": reason}
        self._deleted_logger.info(entry)
        self.logger.info("🗑️ حذف/فیلتر | گروه: %s(%s) | کاربر: %s(%s) | پیام: %s | علت: %s",
            group_title, group_id, username, user_id, message_id, reason, extra=self._extra)

    def log_action(self, action: str, user_id: int, group_id: int, details: str = ""):
        self._actions_logger.info({"action": action, "user_id": user_id,
            "group_id": group_id, "details": details})
        self.logger.warning("⚙️ اقدام مدیریتی | %s | کاربر %s در گروه %s | %s",
            action, user_id, group_id, details, extra=self._extra)

    def log_info(self, message: str):
        text = str(message)
        if self.verbose_logs or important_info(text):
            self.logger.info(text, extra=self._extra)

    def log_error(self, message: str):
        # No blanket error dedup: every real failure remains observable.
        self.logger.error(str(message), extra=self._extra)

    @staticmethod
    def dropped_records() -> int:
        return int(_DroppingQueueHandler.dropped)
