"""Central message dispatch gate.

The message handler in ``core/bot_working_split_ok.py`` runs once per
``(chat_id, message_id)`` because of this module. State below is a
single-process ledger; it does not touch RPC, governor, queue, reconnect,
or the response wrapper. Existing ``message_dedup`` remains the deeper
in-memory seen-set; this gate only enforces the listener-level "exactly
one dispatch per source message" rule, regardless of which route
(priority/command vs group_dispatch) is selected.
"""
import threading
import time

from modules.group_id import normalize_group_id


_LOCK = threading.Lock()
_DISPATCHED = {}
_TTL_SECONDS = 90.0
_MAX_KEYS = 4000


def _key(chat_id, message_id):
    try:
        if chat_id is None or message_id is None:
            return None
        return (normalize_group_id(chat_id), int(message_id))
    except (TypeError, ValueError):
        return None


def _purge(now):
    cutoff = now - _TTL_SECONDS
    if len(_DISPATCHED) <= _MAX_KEYS:
        expired = [k for k, t in _DISPATCHED.items() if t < cutoff]
        for k in expired:
            _DISPATCHED.pop(k, None)
        return
    keys = sorted(_DISPATCHED, key=lambda k: _DISPATCHED[k])
    for k in keys:
        _DISPATCHED.pop(k, None)
        if len(_DISPATCHED) <= _MAX_KEYS:
            break


def claim_dispatch(chat_id, message_id):
    """Atomically mark a chat/message as dispatched.

    Returns ``True`` for the first call and ``False`` for every subsequent
    call with the same key. Missing id components are deliberately
    allowed because the gate then has no stable identity to compare.
    """
    key = _key(chat_id, message_id)
    if key is None:
        return True
    now = time.monotonic()
    with _LOCK:
        _purge(now)
        if key in _DISPATCHED:
            return False
        _DISPATCHED[key] = now
        return True


def reset():
    with _LOCK:
        _DISPATCHED.clear()


def is_dispatched(chat_id, message_id):
    key = _key(chat_id, message_id)
    if key is None:
        return False
    now = time.monotonic()
    with _LOCK:
        _purge(now)
        return key in _DISPATCHED


def dispatched_count():
    with _LOCK:
        return len(_DISPATCHED)
