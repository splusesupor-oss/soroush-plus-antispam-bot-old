"""Independent repeated-GIF detector for SPlusthon messages."""
from collections import defaultdict, deque
import hashlib
import json


GIF_HISTORY = defaultdict(lambda: deque(maxlen=5))


def _document_from_message(message):
    return (
        getattr(message, "document", None)
        or getattr(getattr(message, "media", None), "document", None)
    )


def _animation_attributes(document):
    attributes = getattr(document, "attributes", None) or []
    return [
        attribute.to_dict() if hasattr(attribute, "to_dict")
        else attribute.__class__.__name__
        for attribute in attributes
        if "Animated" in attribute.__class__.__name__
    ]


def get_gif_media_id(message):
    """Return a document ID only to identify animated SPlusthon media."""
    document = _document_from_message(message)
    if not document:
        return None

    mime_type = (getattr(document, "mime_type", None) or "").lower()
    is_gif = bool(getattr(message, "gif", False)) or bool(
        getattr(message, "animation", None)
    ) or mime_type == "image/gif" or bool(_animation_attributes(document))

    if not is_gif:
        return None

    return getattr(document, "id", None) or getattr(
        getattr(message, "file", None), "id", None
    )


async def get_gif_fingerprint(client, message):
    """Return a stable GIF fingerprint independent from document.id."""
    document = _document_from_message(message)
    if not document or get_gif_media_id(message) is None:
        return None, None

    try:
        media_bytes = await client.download_media(message, file=bytes)
        if media_bytes:
            return hashlib.sha256(media_bytes).hexdigest(), "sha256_media_bytes"
    except Exception:
        pass

    metadata = {
        "file_id": getattr(getattr(message, "file", None), "id", None),
        "size": getattr(document, "size", None),
        "mime_type": getattr(document, "mime_type", None),
        "animation_attributes": _animation_attributes(document),
        "access_hash": getattr(document, "access_hash", None),
    }
    # Document IDs are intentionally excluded: SPlusthon may change them.
    fingerprint = hashlib.sha256(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()
    return fingerprint, "metadata_fallback"


def reset_gif_history(chat_id, user_id):
    GIF_HISTORY.pop((chat_id, user_id), None)


def get_gif_event_info(message, chat_id, user_id, fingerprint=None, source=None):
    document = _document_from_message(message)
    return {
        "message_id": getattr(message, "id", None),
        "media_class": getattr(getattr(message, "media", None), "__class__", type(None)).__name__,
        "mime_type": getattr(document, "mime_type", None) if document else None,
        "document_id": getattr(document, "id", None) if document else None,
        "file_id": getattr(getattr(message, "file", None), "id", None),
        "document_size": getattr(document, "size", None) if document else None,
        "animation_attribute": _animation_attributes(document) if document else [],
        "fingerprint": fingerprint,
        "fingerprint_source": source,
        "current_history": list(GIF_HISTORY.get((chat_id, user_id), [])),
    }


def track_gif(chat_id, user_id, message_id, fingerprint):
    """Store a GIF fingerprint and return five repeated message IDs."""
    key = (chat_id, user_id)
    history = GIF_HISTORY[key]

    if history and history[-1][0] != fingerprint:
        history.clear()

    if not history:
        print(f"GIF TRACK START chat_id={chat_id} user_id={user_id}")

    history.append((fingerprint, message_id))
    print(f"GIF HASH={fingerprint}")
    print(f"GIF COUNT={len(history)}")

    if len(history) == 5 and len({item[0] for item in history}) == 1:
        return [item[1] for item in history]
    return None
