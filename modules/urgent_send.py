"""Dedicated send path for short user-facing replies.

SIMPLE_REPLIES / greetings / ``event.reply`` of a short payload must not
wait behind the outgoing RPC gate, moderation notices, or cleanup sends.

This module does **not** change spam detection, moderation policy,
dispatch lanes, keepalive, or handler command logic. It only marks the
outgoing send as ``urgent`` so ``outgoing_rpc`` can skip the heavy gate
and put the packet in front of delete/ban/notice.
"""
from modules.outgoing_rpc import URGENT, current_priority, urgent_rpc


# Longest SIMPLE_REPLIES value is the «روباه» intro (~80 chars).
URGENT_MAX_CHARS = 160

# Cleanup / ban / broadcast notices must stay on the limited LOW path
# even when the template itself is short.
_HEAVY_MARKERS = (
    "هرزنامه",
    "پاک شد",
    "اخراج شد",
    "تبلیغاتی",
    "پشت سر هم",
    "پاکسازی",
    "اطلاع رسانی",
    "فعال سازی شد",
)


def _simple_reply_values():
    try:
        from modules.simple_replies import INSULT_REPLY, SIMPLE_REPLIES
    except Exception:
        return frozenset()
    values = set(SIMPLE_REPLIES.values())
    values.add(INSULT_REPLY)
    return frozenset(values)


_SIMPLE_VALUES = None


def _known_simple_replies():
    global _SIMPLE_VALUES
    if _SIMPLE_VALUES is None:
        _SIMPLE_VALUES = _simple_reply_values()
    return _SIMPLE_VALUES


def is_urgent_text(text):
    """True for a short user-facing reply that must bypass the heavy gate."""
    if not isinstance(text, str):
        return False
    payload = text.strip()
    if not payload:
        return False
    if payload in _known_simple_replies():
        return True
    if len(payload) > URGENT_MAX_CHARS:
        return False
    return not any(marker in payload for marker in _HEAVY_MARKERS)


def extract_send_text(args, kwargs):
    """Best-effort text of ``send_message(entity, message, ...)``."""
    if args:
        if len(args) >= 2 and isinstance(args[1], str):
            return args[1]
    value = kwargs.get("message")
    if value is None:
        value = kwargs.get("text")
    if isinstance(value, str):
        return value
    return ""


async def urgent_send(client, entity, text, **kwargs):
    """Send on the urgent lane: skip the LOW send gate."""
    with urgent_rpc():
        return await client.send_message(entity, text, **kwargs)


async def reply_urgent(event, text, **kwargs):
    """Reply on the urgent lane even if ``event.reply`` was not wrapped."""
    with urgent_rpc():
        reply = getattr(event, "reply", None)
        if callable(reply):
            return await reply(text, **kwargs)
        client = getattr(event, "client", None)
        chat_id = getattr(event, "chat_id", None)
        if client is None:
            message = getattr(event, "message", None)
            client = getattr(message, "client", None) if message is not None else None
            if chat_id is None and message is not None:
                chat_id = getattr(message, "chat_id", None)
        if client is None:
            raise RuntimeError("reply_urgent: no client on event")
        return await client.send_message(chat_id, text, **kwargs)


def should_mark_send_urgent(args, kwargs):
    if current_priority() == URGENT:
        return False
    return is_urgent_text(extract_send_text(args, kwargs))
