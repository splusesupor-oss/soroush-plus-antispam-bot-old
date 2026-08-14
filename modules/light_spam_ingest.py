"""Sync light-path spam ingest that runs before GroupDispatcher.

Only ``chat_id``, ``user_id``, ``message_id`` and the raw text are used.
No RPC, no ``get_sender`` / ``get_chat``, no profile/games, no per-message log.
"""
from modules import big_spam
from modules import message_tracker
from modules.group_dispatch import PRIORITY_ADMIN, classify_priority


class IngestResult:
    __slots__ = ("skip_heavy", "detected", "reason", "tracked")

    def __init__(self, skip_heavy, detected, reason="", tracked=False):
        self.skip_heavy = bool(skip_heavy)
        self.detected = bool(detected)
        self.reason = reason or ""
        self.tracked = bool(tracked)


def extract_event(event):
    """Read ids and text from the event object only. Never awaits."""
    message = getattr(event, "message", None)
    chat_id = getattr(event, "chat_id", None)
    message_id = getattr(message, "id", None) if message is not None else None
    text = ""
    if message is not None:
        text = (
            getattr(message, "message", None)
            or getattr(message, "caption", None)
            or ""
        )
    user_id = getattr(event, "sender_id", None)
    if user_id is None:
        sender = getattr(event, "sender", None)
        user_id = getattr(sender, "id", None)
    is_private = bool(getattr(event, "is_private", False))
    return chat_id, user_id, message_id, text, is_private


def _cheap_admin_bypass(bot, chat_id, user_id):
    """Registered owner/admin only. Never calls the network."""
    probe = getattr(bot, "_light_admin_bypass", None)
    if callable(probe):
        try:
            return bool(probe(chat_id, user_id))
        except Exception:
            return False
    if user_id is None:
        return False
    if user_id == getattr(bot, "bot_account_id", None):
        return True
    try:
        from modules.admin_tools import has_admin_permission
        if has_admin_permission(chat_id, user_id, None):
            return True
    except Exception:
        pass
    cache = getattr(bot, "native_group_admin_cache", None)
    if cache:
        try:
            from modules.group_id import normalize_group_id
            cached = cache.get((normalize_group_id(chat_id), str(user_id)))
            if cached and cached[0]:
                return True
        except Exception:
            pass
    return False


def _capture(bot, chat_id, user_id, message_id):
    incidents = getattr(bot, "_big_spam_incidents", None)
    if not incidents:
        return
    incident = incidents.get((chat_id, user_id))
    if incident is not None and isinstance(message_id, int) and message_id > 0:
        incident["ids"].add(message_id)


def _start_wave(bot, event, chat_id, user_id, ids, reason):
    starter = getattr(bot, "_queue_big_spam_ban", None)
    if callable(starter):
        return starter(event, chat_id, user_id, None, ids, reason)
    from handlers.message_handler import _queue_big_spam_ban
    return _queue_big_spam_ban(bot, event, chat_id, user_id, None, ids, reason)


def ingest(bot, chat_id, user_id, message_id, text, *, event=None, is_private=False):
    """Track + detect. ``skip_heavy`` means do not enqueue the full handler."""
    try:
        return _ingest(
            bot, chat_id, user_id, message_id, text,
            event=event, is_private=is_private,
        )
    except Exception:
        return IngestResult(skip_heavy=False, detected=False)


def ingest_event(bot, event):
    chat_id, user_id, message_id, text, is_private = extract_event(event)
    return ingest(
        bot, chat_id, user_id, message_id, text,
        event=event, is_private=is_private,
    )


def _ingest(bot, chat_id, user_id, message_id, text, *, event=None, is_private=False):
    priority, _kind = classify_priority(text)
    if priority <= PRIORITY_ADMIN:
        return IngestResult(skip_heavy=False, detected=False)
    if is_private:
        return IngestResult(skip_heavy=False, detected=False)
    if chat_id is None or message_id is None or user_id is None:
        return IngestResult(skip_heavy=False, detected=False)
    if not str(text or "").strip():
        return IngestResult(skip_heavy=False, detected=False)
    if _cheap_admin_bypass(bot, chat_id, user_id):
        return IngestResult(skip_heavy=False, detected=False)

    key = (chat_id, user_id)
    incidents = getattr(bot, "_big_spam_incidents", {}) or {}
    if key in incidents:
        tracked = message_tracker.add_message(chat_id, user_id, message_id, text)
        _capture(bot, chat_id, user_id, message_id)
        return IngestResult(
            skip_heavy=True, detected=True, tracked=tracked,
        )

    tracked = message_tracker.add_message(chat_id, user_id, message_id, text)
    rows = message_tracker.get_user_recent_messages(chat_id, user_id)
    hit, reason, ids = big_spam.detect_big_spam(text, rows)
    if not hit:
        return IngestResult(skip_heavy=False, detected=False, tracked=tracked)

    if isinstance(message_id, int) and message_id > 0:
        ids.add(message_id)
    _start_wave(bot, event, chat_id, user_id, ids, reason)
    return IngestResult(
        skip_heavy=True, detected=True, reason=reason, tracked=tracked,
    )
