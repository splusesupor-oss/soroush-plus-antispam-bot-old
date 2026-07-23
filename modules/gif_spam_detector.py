"""Independent repeated-GIF detector for SPlusthon messages."""
from collections import defaultdict, deque


GIF_HISTORY = defaultdict(lambda: deque(maxlen=5))


def _document_from_message(message):
    return (
        getattr(message, "document", None)
        or getattr(getattr(message, "media", None), "document", None)
    )


def get_gif_media_id(message):
    """Return a stable SPlusthon GIF/animation document ID, or None."""
    document = _document_from_message(message)
    if not document:
        return None

    mime_type = (getattr(document, "mime_type", None) or "").lower()
    attributes = getattr(document, "attributes", None) or []
    animated_attribute = any(
        "Animated" in attribute.__class__.__name__
        for attribute in attributes
    )
    is_gif = bool(getattr(message, "gif", False)) or bool(
        getattr(message, "animation", None)
    ) or mime_type == "image/gif" or animated_attribute

    if not is_gif:
        return None

    return getattr(document, "id", None) or getattr(
        getattr(message, "file", None), "id", None
    )


def reset_gif_history(chat_id, user_id):
    GIF_HISTORY.pop((chat_id, user_id), None)


def track_gif(chat_id, user_id, message_id, media_id):
    """Store a GIF and return five repeated message IDs when detected."""
    key = (chat_id, user_id)
    history = GIF_HISTORY[key]

    if history and history[-1][0] != media_id:
        history.clear()

    if not history:
        print(f"GIF TRACK START chat_id={chat_id} user_id={user_id}")

    history.append((media_id, message_id))
    print(f"GIF HASH={media_id}")
    print(f"GIF COUNT={len(history)}")

    if len(history) == 5 and len({item[0] for item in history}) == 1:
        return [item[1] for item in history]
    return None
