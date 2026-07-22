import time
from collections import defaultdict

ATTACK_HISTORY = defaultdict(list)

def check_attack(user_id, message_text, limit=10, seconds=5):
    try:
        now = time.time()

        ATTACK_HISTORY[user_id] = [
            x for x in ATTACK_HISTORY[user_id]
            if now - x < seconds
        ]

        ATTACK_HISTORY[user_id].append(now)

        # ارسال تعداد زیاد پیام در زمان کوتاه
        if len(ATTACK_HISTORY[user_id]) >= limit:
            return True

        return False

    except Exception:
        return False


def clear_attack(user_id):
    try:
        if user_id in ATTACK_HISTORY:
            ATTACK_HISTORY.pop(user_id)
    except Exception:
        pass
