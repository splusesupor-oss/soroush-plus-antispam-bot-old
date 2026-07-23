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


def clear(owner_id):
    _PENDING_BROADCASTS.pop(str(owner_id), None)
