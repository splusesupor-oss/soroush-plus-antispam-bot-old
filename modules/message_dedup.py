"""Per-chat message_id dedup so one group event cannot produce two replies.

SPlusthon delivers the same group message as NewMessage and again as
MessageEdited. Both are bound to the same handler, so "ربات" was answered
twice (simple reply + a second friendly_reply roll). PV traffic is not
deduped by this module; the caller skips it.
"""
from collections import OrderedDict
import threading
import time

_LOCK = threading.Lock()
_IN_FLIGHT = set()
_SEEN = OrderedDict()
_TTL_SECONDS = 180.0
_MAX_SEEN = 8000


def _key(chat_id, message_id):
    try:
        if chat_id is None or message_id is None:
            return None
        return (int(chat_id), int(message_id))
    except (TypeError, ValueError):
        return None


def _expire(now):
    cutoff = now - _TTL_SECONDS
    while _SEEN:
        key, started = next(iter(_SEEN.items()))
        if started >= cutoff and len(_SEEN) <= _MAX_SEEN:
            break
        _SEEN.popitem(last=False)


def begin(chat_id, message_id):
    """Reserve this event. Return True if it should be processed."""
    key = _key(chat_id, message_id)
    if key is None:
        return True
    now = time.monotonic()
    with _LOCK:
        _expire(now)
        if key in _IN_FLIGHT or key in _SEEN:
            return False
        _IN_FLIGHT.add(key)
        return True


def finish(chat_id, message_id):
    """Mark the event seen so a later NewMessage/MessageEdited is skipped."""
    key = _key(chat_id, message_id)
    if key is None:
        return
    now = time.monotonic()
    with _LOCK:
        _IN_FLIGHT.discard(key)
        _SEEN[key] = now
        _SEEN.move_to_end(key)
        _expire(now)


def reset():
    with _LOCK:
        _IN_FLIGHT.clear()
        _SEEN.clear()


def in_flight_count():
    with _LOCK:
        return len(_IN_FLIGHT)


def seen_count():
    with _LOCK:
        return len(_SEEN)
