"""Simple consecutive GIF spam detector for SPlusthon messages."""
from collections import defaultdict, deque


GIF_COUNTER = defaultdict(lambda: deque(maxlen=5))


def _document_from_message(message):
    return (
        getattr(message, "document", None)
        or getattr(getattr(message, "media", None), "document", None)
    )


def is_gif_message(message):
    document = _document_from_message(message)
    if not document:
        return False

    mime_type = (getattr(document, "mime_type", None) or "").lower()
    attributes = getattr(document, "attributes", None) or []
    animated = any("Animated" in attr.__class__.__name__ for attr in attributes)
    return (
        bool(getattr(message, "gif", False))
        or bool(getattr(message, "animation", None))
        or mime_type == "image/gif"
        or animated
    )


def reset_gif_history(chat_id, user_id):
    GIF_COUNTER.pop((chat_id, user_id), None)


def track_gif(chat_id, user_id, message_id):
    key = (chat_id, user_id)
    history = GIF_COUNTER[key]
    history.append(message_id)
    print(f"GIF COUNT={len(history)}")

    if len(history) == 5:
        return list(history)
    return None
