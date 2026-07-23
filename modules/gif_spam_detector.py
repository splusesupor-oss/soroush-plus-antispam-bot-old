"""Independent consecutive GIF spam detector for SPlusthon messages."""
from collections import defaultdict, deque


GIF_HISTORY = defaultdict(lambda: deque(maxlen=5))


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
    key = (chat_id, user_id)
    if key in GIF_HISTORY:
        print(f"GIF HISTORY RESET key={key} deque_id={id(GIF_HISTORY[key])}")
    GIF_HISTORY.pop(key, None)


def track_gif(chat_id, user_id, message_id):
    """Track every consecutive GIF; return five message IDs at threshold."""
    key = (chat_id, user_id)
    history = GIF_HISTORY[key]
    history_before = list(history)
    if not history:
        print(f"GIF TRACK START chat_id={chat_id} user_id={user_id}")

    history.append(message_id)
    print(
        "GIF STATE DEBUG\n"
        f"chat_id={chat_id}\n"
        f"user_id={user_id}\n"
        f"history_key={key}\n"
        f"history_before={history_before}\n"
        f"history_after={list(history)}\n"
        f"history_deque_id={id(history)}"
    )
    print(f"GIF COUNT={len(history)}")

    if len(history) == 5:
        return list(history)
    return None
