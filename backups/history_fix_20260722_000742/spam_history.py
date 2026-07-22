import re
import time
from collections import defaultdict, deque

# آخرین پیام‌های هر کاربر
MESSAGE_HISTORY = defaultdict(lambda: deque(maxlen=150))

# آیدی پیام‌های حذف شده برای پاکسازی گروهی
USER_MESSAGE_IDS = defaultdict(lambda: deque(maxlen=5000))


def normalize(text: str) -> str:
    if not text:
        return ""

    text = text.lower()

    text = text.replace("ي", "ی")
    text = text.replace("ك", "ک")

    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)

    text = re.sub(r'@\w+', '', text)

    text = re.sub(r'[^\w\sآ-ی]', ' ', text)

    text = re.sub(r'(.)\1{3,}', r'\1', text)

    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def add_message(chat_id, user_id, message_id, text):

    key = (chat_id, user_id)

    USER_MESSAGE_IDS[key].append(message_id)

    MESSAGE_HISTORY[key].append({
        "text": normalize(text),
        "time": time.time(),
        "raw": text
    })


def is_repeat(chat_id, user_id, text,
              min_repeat=4,
              seconds=120):

    key = (chat_id, user_id)

    now = time.time()

    norm = normalize(text)

    count = 0

    for item in MESSAGE_HISTORY[key]:

        if now - item["time"] > seconds:
            continue

        if item["text"] == norm:
            count += 1

    return count >= min_repeat


def get_message_ids(chat_id, user_id):

    return list(USER_MESSAGE_IDS.get((chat_id, user_id), []))


def clear_user(chat_id, user_id):

    MESSAGE_HISTORY.pop((chat_id, user_id), None)

    USER_MESSAGE_IDS.pop((chat_id, user_id), None)
