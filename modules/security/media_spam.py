import time

MEDIA_HISTORY = {}

MAX_MEDIA = 5
TIME_WINDOW = 10


def check_media_spam(user_id, message):
    try:
        now = time.time()

        if user_id not in MEDIA_HISTORY:
            MEDIA_HISTORY[user_id] = []

        MEDIA_HISTORY[user_id] = [
            x for x in MEDIA_HISTORY[user_id]
            if now - x < TIME_WINDOW
        ]

        has_media = False

        if getattr(message, "file", None):
            has_media = True

        if not has_media:
            return False

        MEDIA_HISTORY[user_id].append(now)

        if len(MEDIA_HISTORY[user_id]) >= MAX_MEDIA:
            return True

        return False

    except Exception:
        return False


def clear_media(user_id):
    try:
        MEDIA_HISTORY.pop(user_id, None)
    except Exception:
        pass
