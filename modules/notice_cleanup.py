"""Per-group auto-cleanup of bot system notices after a fixed TTL.

Only automatic moderation/spam notices belong here. Command replies, manual
admin warnings and ordinary chat are never scheduled.

Each group has its own worker and expiry heap, so a flood of notices in
group A cannot delay the 60-second delete in group B.  The incoming-message
dispatcher is never used: ``schedule`` is synchronous and only wakes that
group's worker.  Persistence is flushed by the worker, not the sender.
"""
import asyncio
import json
import os
import tempfile
import time

DEFAULT_TTL_SECONDS = 60
MAX_PER_CHAT = 500


def _chat_key(chat_id):
    if chat_id is None:
        return "0"
    for attr in ("channel_id", "chat_id", "user_id", "id"):
        try:
            val = getattr(chat_id, attr, None)
            if isinstance(val, int):
                try:
                    from modules.group_id import normalize_group_id
                    return normalize_group_id(val)
                except Exception:
                    return str(val)
            if val is not None:
                try:
                    ival = int(val)
                    try:
                        from modules.group_id import normalize_group_id
                        return normalize_group_id(ival)
                    except Exception:
                        return str(ival)
                except Exception:
                    return str(val)
        except Exception:
            continue
    try:
        ival = int(chat_id)
        try:
            from modules.group_id import normalize_group_id
            return normalize_group_id(ival)
        except Exception:
            return str(ival)
    except Exception:
        pass
    try:
        return str(chat_id)
    except Exception:
        return "0" 


def _chat_id_for_rpc(key):
    try:
        return int(key)
    except (TypeError, ValueError):
        return key


def extract_sent_id(sent):
    """Read a Soroush/SPlusthon send/reply result as a positive message id."""
    if sent is None or isinstance(sent, bool):
        return None
    if isinstance(sent, int):
        return sent if sent > 0 else None
    for attr in ("id", "message_id"):
        value = getattr(sent, attr, None)
        if isinstance(value, int) and value > 0:
            # Skip peer/channel objects whose .id is not this message.
            if attr == "id" and getattr(sent, "message", None) is sent:
                continue
            cls_name = type(sent).__name__
            if attr == "id" and ("Peer" in cls_name or "User" in cls_name or "Channel" in cls_name or "Chat" in cls_name):
                continue
            if cls_name.endswith("Message") or attr == "message_id" or hasattr(sent, "peer_id") or hasattr(sent, "out"):
                return value
            if cls_name == "SimpleNamespace":
                return value
    inner = getattr(sent, "message", None)
    if inner is not None and inner is not sent:
        found = extract_sent_id(inner)
        if found:
            return found
    if isinstance(sent, (list, tuple)):
        for item in sent:
            found = extract_sent_id(item)
            if found:
                return found
    updates = getattr(sent, "updates", None)
    if updates:
        for update in updates:
            found = extract_sent_id(getattr(update, "message", update))
            if found:
                return found
    update = getattr(sent, "update", None)
    if update is not None:
        found = extract_sent_id(getattr(update, "message", update))
        if found:
            return found
    # Last resort: a plain object with a positive .id that looks like a message.
    value = getattr(sent, "id", None)
    if isinstance(value, int) and value > 0 and not hasattr(sent, "access_hash"):
        return value
    return None


def _message_id(value):
    return extract_sent_id(value)


def capture_sent(bot, chat_id, sent):
    """Schedule a just-sent automatic notice. Never awaits."""
    cleanup = getattr(bot, "notice_cleanup", None)
    if cleanup is None:
        return False
    return cleanup.schedule(chat_id, sent)


class NoticeCleanup:
    """Independent per-chat notice TTL workers."""

    def __init__(self, persist_path, logger=None, *, ttl_seconds=DEFAULT_TTL_SECONDS,
                 delete_queue=None):
        self.persist_path = persist_path
        self.logger = logger
        self.ttl_seconds = float(ttl_seconds)
        self.delete_queue = delete_queue
        self._items = {}
        self._workers = {}
        self._events = {}
        self._dirty = False
        self._started = False
        self._load()

    def bind_delete_queue(self, queue):
        self.delete_queue = queue

    def start(self):
        """Launch workers for any persisted notices. Safe to call once."""
        self._started = True
        if self.logger is not None:
            self.logger.log_info(
                "NOTICE CLEANUP START "
                f"ttl_s={self.ttl_seconds:g} "
                f"pending_groups={len(self._items)}"
            )
        for chat_id, rows in list(self._items.items()):
            if rows:
                self._ensure_worker(chat_id)

    def stop(self):
        self._started = False
        for task in list(self._workers.values()):
            task.cancel()
        self._workers.clear()
        if self._dirty:
            self._persist()

    def schedule(self, chat_id, message_id, *, ttl=None, now=None):
        """Remember ``message_id`` for this chat. Returns True if stored."""
        raw = message_id
        message_id = _message_id(message_id)
        if chat_id is None or not isinstance(message_id, int) or message_id <= 0:
            if self.logger is not None:
                self.logger.log_error(
                    "NOTICE CLEANUP ID MISSING "
                    f"chat_id={chat_id} sent_type={type(raw).__name__} "
                    f"sent={raw!r}"
                )
            return False
        key = _chat_key(chat_id)
        ttl_s = float(self.ttl_seconds if ttl is None else ttl)
        expires_at = (time.time() if now is None else float(now)) + ttl_s
        rows = self._items.setdefault(key, [])
        for row in rows:
            if int(row["message_id"]) == message_id:
                row["expires_at"] = expires_at
                row["chat_id"] = chat_id
                break
        else:
            rows.append({
                "message_id": int(message_id),
                "expires_at": expires_at,
                "chat_id": chat_id,
            })
            if len(rows) > MAX_PER_CHAT:
                rows.sort(key=lambda item: item["expires_at"])
                del rows[:-MAX_PER_CHAT]
        self._dirty = True
        self._ensure_worker(key)
        event = self._events.get(key)
        if event is not None and not event.is_set():
            event.set()
        if self.logger is not None:
            self.logger.log_info(
                "NOTICE CLEANUP QUEUED "
                f"chat_id={chat_id} message_id={message_id} "
                f"expires_in_s={ttl_s:g} pending={len(rows)}"
            )
        return True

    def pending(self, chat_id):
        return list(self._items.get(_chat_key(chat_id), []))

    def due_ids(self, chat_id, now=None):
        now = time.time() if now is None else float(now)
        return [
            int(row["message_id"])
            for row in self._items.get(_chat_key(chat_id), [])
            if float(row["expires_at"]) <= now
        ]

    def pop_due(self, chat_id, now=None):
        """Remove and return expired IDs for one chat only."""
        key = _chat_key(chat_id)
        now = time.time() if now is None else float(now)
        rows = self._items.get(key, [])
        due = []
        kept = []
        for row in rows:
            if float(row["expires_at"]) <= now:
                due.append(int(row["message_id"]))
            else:
                kept.append(row)
        if due:
            if kept:
                self._items[key] = kept
            else:
                self._items.pop(key, None)
            self._dirty = True
        return due

    def next_expiry(self, chat_id, now=None):
        rows = self._items.get(_chat_key(chat_id), [])
        if not rows:
            return None
        return min(float(row["expires_at"]) for row in rows)

    def _ensure_worker(self, chat_id):
        if not self._started:
            return
        key = _chat_key(chat_id)
        if key not in self._events:
            self._events[key] = asyncio.Event()
        worker = self._workers.get(key)
        if worker is None or worker.done():
            self._workers[key] = asyncio.create_task(
                self._worker(key), name=f"notice-cleanup-{key}"
            )

    def _enqueue_delete(self, chat_id, message_ids):
        queue = self.delete_queue
        if queue is None or not message_ids:
            return None
        try:
            return queue.enqueue(_chat_id_for_rpc(chat_id), message_ids, priority=1)
        except Exception as error:
            if self.logger is not None:
                self.logger.log_error(
                    f"NOTICE CLEANUP ENQUEUE FAILED chat_id={chat_id} error={error!r}"
                )
            return None

    async def _worker(self, chat_id):
        event = self._events[chat_id]
        if self.logger is not None:
            self.logger.log_info(f"NOTICE CLEANUP START chat_id={chat_id}")
        try:
            while self._started:
                rows = self._items.get(chat_id) or []
                if not rows:
                    event.clear()
                    await event.wait()
                    continue
                now = time.time()
                due = self.pop_due(chat_id, now=now)
                if due:
                    if self.logger is not None:
                        self.logger.log_info(
                            "NOTICE CLEANUP DUE "
                            f"chat_id={chat_id} message_ids={due!r}"
                        )
                    if self._dirty:
                        self._persist()
                    result = self._enqueue_delete(chat_id, due)
                    deleted, remaining = 0, list(due)
                    try:
                        if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                            deleted, remaining = await result
                        elif result is not None and not isinstance(result, bool):
                            deleted, remaining = result
                        elif result:
                            deleted, remaining = len(due), []
                    except Exception as error:
                        if self.logger is not None:
                            self.logger.log_error(
                                "NOTICE CLEANUP DELETE FAILED "
                                f"chat_id={chat_id} message_ids={due!r} error={error!r}"
                            )
                    else:
                        if self.logger is not None:
                            self.logger.log_info(
                                "NOTICE CLEANUP DELETED "
                                f"chat_id={chat_id} message_ids={due!r} "
                                f"deleted={deleted} remaining={len(remaining or ())}"
                            )
                    continue
                next_at = self.next_expiry(chat_id)
                if next_at is None:
                    continue
                delay = max(0.01, next_at - now)
                event.clear()
                try:
                    await asyncio.wait_for(event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if self.logger is not None:
                self.logger.log_error(
                    f"NOTICE CLEANUP WORKER FAILED chat_id={chat_id} error={error!r}"
                )
        finally:
            if self._workers.get(chat_id) is asyncio.current_task():
                self._workers.pop(chat_id, None)
            if self._dirty:
                self._persist()

    def _load(self):
        path = self.persist_path
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle) or {}
        except Exception as error:
            if self.logger is not None:
                self.logger.log_error(f"NOTICE CLEANUP LOAD FAILED error={error!r}")
            return
        items = {}
        if isinstance(raw, dict):
            for key, rows in raw.items():
                cleaned = []
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    message_id = row.get("message_id")
                    expires_at = row.get("expires_at")
                    if not isinstance(message_id, int) or message_id <= 0:
                        continue
                    try:
                        expires_at = float(expires_at)
                    except (TypeError, ValueError):
                        continue
                    item = {"message_id": message_id, "expires_at": expires_at}
                    if row.get("chat_id") is not None:
                        item["chat_id"] = row.get("chat_id")
                    cleaned.append(item)
                if cleaned:
                    items[_chat_key(key)] = cleaned
        self._items = items

    def _persist(self):
        path = self.persist_path
        if not path:
            self._dirty = False
            return
        payload = {
            key: list(rows) for key, rows in self._items.items() if rows
        }
        directory = os.path.dirname(path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            handle, tmp_path = tempfile.mkstemp(
                prefix="notice_cleanup.", suffix=".tmp", dir=directory
            )
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as tmp:
                    json.dump(payload, tmp, ensure_ascii=False)
                    tmp.write("\n")
                os.replace(tmp_path, path)
                self._dirty = False
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as error:
            if self.logger is not None:
                self.logger.log_error(
                    f"NOTICE CLEANUP SAVE FAILED error={error!r}"
                )
