from collections import defaultdict, deque
import re
import time


MESSAGE_HISTORY = defaultdict(lambda: deque(maxlen=2000))
REPEAT_WINDOW_SECONDS = 30
# 🧹 نگه‌داری تاریخچه هر کاربر حداکثر ۳۰ دقیقه بعد از آخرین پیامش.
# بدون این، در گروه‌های پرترافیک (لینکدونی) تاریخچهٔ صدها کاربر ×
# تا ۲۰۰۰ رکورد متنی برای همیشه در RAM می‌ماند؛ بعد از یکی-دو ساعت
# حافظه چند صد مگابایت می‌شد، اندروید پروسه را swap می‌کرد و ربات
# به‌تدریج کند می‌شد (همان الگوی «بعد از ری‌استارت یک ساعت خوب است»).
# همهٔ مصرف‌کننده‌ها فقط به پنجره‌های کوتاه نیاز دارند
# (is_repeat=۳۰ ثانیه، بررسی موج اسپم=چند دقیقه).
RETENTION_SECONDS = 30 * 60


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


def cleanup_expired(now=None, retention=RETENTION_SECONDS):
    """هرس دوره‌ای تاریخچه‌های راکد؛ داده‌های تازهٔ تشخیص دست نمی‌خورد.

    از حلقهٔ پاکسازی ۶۰ ثانیه‌ای core صدا زده می‌شود (مثل
    message_tracker.cleanup_expired). کاربری که در ۳۰ دقیقهٔ اخیر پیام
    داده، رکوردهای تازه‌اش می‌ماند؛ رکوردهای قدیمی‌ترش و کاربران راکد
    کامل آزاد می‌شوند تا RAM در گروه‌های پرترافیک رشد بی‌پایان نکند.
    """
    now = time.monotonic() if now is None else now
    removed_rows = 0
    for key in list(MESSAGE_HISTORY.keys()):
        rows = MESSAGE_HISTORY.get(key)
        if not rows:
            MESSAGE_HISTORY.pop(key, None)
            continue
        fresh = [
            item for item in rows
            if now - item.get("timestamp", now) <= retention
        ]
        removed_rows += len(rows) - len(fresh)
        if fresh:
            if len(fresh) != len(rows):
                MESSAGE_HISTORY[key] = deque(fresh, maxlen=2000)
        else:
            MESSAGE_HISTORY.pop(key, None)
    return removed_rows
