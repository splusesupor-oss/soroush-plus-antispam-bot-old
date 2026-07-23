"""Temporary private broadcast state for the global bot owner."""


_PENDING_BROADCASTS = {}


def begin(owner_id):
    _PENDING_BROADCASTS[str(owner_id)] = {"phase": "awaiting_message"}


def get(owner_id):
    return _PENDING_BROADCASTS.get(str(owner_id))


def set_message(owner_id, text):
    _PENDING_BROADCASTS[str(owner_id)] = {
        "phase": "awaiting_confirmation",
        "text": text,
    }


def set_sending(owner_id):
    state = _PENDING_BROADCASTS.get(str(owner_id))
    if not state or state.get("phase") != "awaiting_confirmation":
        return None
    state["phase"] = "sending"
    return state["text"]


def clear(owner_id):
    _PENDING_BROADCASTS.pop(str(owner_id), None)
