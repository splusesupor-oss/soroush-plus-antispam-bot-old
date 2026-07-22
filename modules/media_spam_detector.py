import time

MEDIA_HISTORY = {}

def check_media_spam(user_id, message):
    try:
        now = time.time()

        if user_id not in MEDIA_HISTORY:
            MEDIA_HISTORY[user_id] = []

        media = getattr(message, "media", None)

        if not media:
            return False

        MEDIA_HISTORY[user_id].append(now)

        MEDIA_HISTORY[user_id] = [
            x for x in MEDIA_HISTORY[user_id]
            if now - x <= 10
        ]

        return len(MEDIA_HISTORY[user_id]) >= 5

    except Exception:
        return False
