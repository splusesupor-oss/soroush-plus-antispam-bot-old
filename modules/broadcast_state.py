"""Single-session temporary broadcast state for the global bot owner."""


_PENDING_BROADCASTS = {}


def clear(owner_id):
    """Destroy every temporary broadcast value for this owner."""
    _PENDING_BROADCASTS.pop(str(owner_id), None)


def begin(owner_id):
    """Start a brand-new session, replacing any stale one."""
    clear(owner_id)
    _PENDING_BROADCASTS[str(owner_id)] = {"phase": "awaiting_message"}


def get(owner_id):
    return _PENDING_BROADCASTS.get(str(owner_id))


def set_message(owner_id, text):
    _PENDING_BROADCASTS[str(owner_id)] = {
        "phase": "awaiting_confirmation",
        "text": text,
    }


def consume_confirmation(owner_id):
    """Atomically consume the only valid confirmation and destroy its state."""
    state = _PENDING_BROADCASTS.get(str(owner_id))
    if not state or state.get("phase") != "awaiting_confirmation":
        return None
    text = state.get("text")
    clear(owner_id)
    return text
