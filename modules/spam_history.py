from collections import defaultdict, deque
import re
import time


MESSAGE_HISTORY = defaultdict(lambda: deque(maxlen=2000))
USER_MESSAGE_IDS = defaultdict(lambda: deque(maxlen=2000))
REPEAT_WINDOW_SECONDS = 30


def normalize(text):
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\wآ-ی ]', '', text)
    return text.strip()


def save_history_message(chat_id, user_id, message_id, text):
    key = (chat_id, user_id)
    MESSAGE_HISTORY[key].append((normalize(text), time.monotonic()))
    if message_id not in USER_MESSAGE_IDS[key]:
        USER_MESSAGE_IDS[key].append(message_id)


def is_repeat(chat_id, user_id, text, limit=3):
    key = (chat_id, user_id)
    current = normalize(text)
    if not current:
        return False

    now = time.monotonic()
    recent_count = sum(
        1
        for saved_text, saved_at in MESSAGE_HISTORY.get(key, [])
        if saved_text == current and now - saved_at <= REPEAT_WINDOW_SECONDS
    )
    return recent_count >= limit


def get_message_ids(chat_id, user_id):
    return list(USER_MESSAGE_IDS.get((chat_id, user_id), []))


def clear_user(chat_id, user_id):
    MESSAGE_HISTORY.pop((chat_id, user_id), None)
    USER_MESSAGE_IDS.pop((chat_id, user_id), None)
