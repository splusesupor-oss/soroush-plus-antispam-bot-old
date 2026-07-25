"""Name & Family group game state and validation."""
import random
from modules.game_points import add

LETTERS = list("ابتثجچحخدذرزسشصضطظعغفقکگلمنوهی")
CATEGORIES = ("نام", "فامیل", "شهر", "میوه", "وسیله", "حیوان", "خواننده")
_ACTIVE = {}


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id):
    if chat_id in _ACTIVE:
        return None
    state = {"letter": random.SystemRandom().choice(LETTERS), "answers": {}}
    _ACTIVE[chat_id] = state
    return dict(state)


def _normalize(value):
    return value.strip().replace("ي", "ی").replace("ك", "ک").replace("‌", " ")


def submit(chat_id, user_id, name, text):
    state = _ACTIVE.get(chat_id)
    if not state:
        return None
    parts = [part.strip() for part in text.replace("|", "\n").replace("،", "\n").splitlines() if part.strip()]
    if len(parts) != len(CATEGORIES):
        return None
    letter = state["letter"]
    valid = [part for part in parts if _normalize(part).startswith(letter)]
    if not valid:
        return None
    points = len(valid) * 10
    state["answers"][str(user_id)] = {"name": name, "points": points}
    add(chat_id, user_id, name, points)
    return points


def finish(chat_id):
    state = _ACTIVE.pop(chat_id, None)
    if not state:
        return []
    return sorted(state["answers"].values(), key=lambda item: item["points"], reverse=True)
