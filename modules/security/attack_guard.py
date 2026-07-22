import time

ATTACK_HISTORY = {}

ATTACK_LIMIT = 20
ATTACK_TIME = 5


def check_attack(user_id):
    try:
        now = time.time()

        if user_id not in ATTACK_HISTORY:
            ATTACK_HISTORY[user_id] = []

        ATTACK_HISTORY[user_id] = [
            t for t in ATTACK_HISTORY[user_id]
            if now - t <= ATTACK_TIME
        ]

        ATTACK_HISTORY[user_id].append(now)

        if len(ATTACK_HISTORY[user_id]) >= ATTACK_LIMIT:
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
