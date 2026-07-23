from collections import defaultdict, deque
import re
import time


MESSAGE_HISTORY = defaultdict(lambda: deque(maxlen=2000))
REPEAT_WINDOW_SECONDS = 30


def normalize(text):
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\wآ-ی ]', '', text)
    return text.strip()


def save_history_message(chat_id, user_id, message_id, text):
    key = (chat_id, user_id)
    if message_id is None:
        return False

    normalized_text = normalize(text)
    if any(item["message_id"] == message_id for item in MESSAGE_HISTORY[key]):
        return False

    MESSAGE_HISTORY[key].append({
        "message_id": message_id,
        "normalized_text": normalized_text,
        "timestamp": time.monotonic(),
    })
    return True


def get_user_history(chat_id, user_id):
    key = (chat_id, user_id)
    if key not in MESSAGE_HISTORY:
        return None
    return list(MESSAGE_HISTORY[key])


def is_repeat(chat_id, user_id, text, limit=3):
    current = normalize(text)
    if not current:
        return False

    now = time.monotonic()
    recent_count = sum(
        1
        for item in MESSAGE_HISTORY.get((chat_id, user_id), [])
        if (
            item["normalized_text"] == current
            and now - item["timestamp"] <= REPEAT_WINDOW_SECONDS
        )
    )
    return recent_count >= limit


def get_message_ids(chat_id, user_id):
    return [
        item["message_id"]
        for item in MESSAGE_HISTORY.get((chat_id, user_id), [])
    ]


def clear_user(chat_id, user_id):
    MESSAGE_HISTORY.pop((chat_id, user_id), None)
