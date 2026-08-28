"""Message and response deduplication for one process.

SPlusthon can deliver the same update through more than one event path
(``NewMessage``/``MessageEdited``), and a reconnect can replay an update.
The incoming reservation ensures that only one path processes a message.
The response reservation is a second, send-side gate: one source message can
claim at most one outgoing reply.
"""
from collections import OrderedDict
import threading
import time

from modules.group_id import normalize_group_id

_LOCK = threading.Lock()
_IN_FLIGHT = set()
_SEEN = OrderedDict()
_RESPONSE_CLAIMED = OrderedDict()
_TTL_SECONDS = 180.0
_MAX_SEEN = 8000


def _key(chat_id, message_id):
    try:
        if chat_id is None or message_id is None:
            return None
        # The same group may arrive as its short id or its -100 channel id.
        return (normalize_group_id(chat_id), int(message_id))
    except (TypeError, ValueError):
        return None


def _expire(now):
    cutoff = now - _TTL_SECONDS
    while _SEEN:
        key, started = next(iter(_SEEN.items()))
        if started >= cutoff and len(_SEEN) <= _MAX_SEEN:
            break
        _SEEN.popitem(last=False)
    while _RESPONSE_CLAIMED:
        key, started = next(iter(_RESPONSE_CLAIMED.items()))
        if started >= cutoff and len(_RESPONSE_CLAIMED) <= _MAX_SEEN:
            break
        _RESPONSE_CLAIMED.popitem(last=False)


def _valid_key(chat_id, message_id):
    return _key(chat_id, message_id)


def claim_response(chat_id, message_id):
    """Atomically claim the single reply slot for a source message.

    Returns ``True`` for the first sender and ``False`` for every later sender.
    Missing IDs are deliberately allowed because an unknown source cannot be
    safely correlated with another message.
    """
    key = _valid_key(chat_id, message_id)
    if key is None:
        return True
    now = time.monotonic()
    with _LOCK:
        _expire(now)
        if key in _RESPONSE_CLAIMED:
            return False
        _RESPONSE_CLAIMED[key] = now
        return True


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


def release_response(chat_id, message_id):
    """Release a claim only when the underlying send failed before delivery."""
    key = _key(chat_id, message_id)
    if key is None:
        return
    with _LOCK:
        _RESPONSE_CLAIMED.pop(key, None)


def reset():
    with _LOCK:
        _IN_FLIGHT.clear()
        _SEEN.clear()
        _RESPONSE_CLAIMED.clear()


def in_flight_count():
    with _LOCK:
        return len(_IN_FLIGHT)


def seen_count():
    with _LOCK:
        return len(_SEEN)
