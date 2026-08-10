"""سابقهٔ سریع پیام‌ها برای پاکسازی موج اسپم، مستقل از punishment."""
from collections import defaultdict, deque
import re
import time

_MAX = 100
_WINDOW = 120
_HISTORY = defaultdict(lambda: deque(maxlen=_MAX))


def _norm(text):
    return " ".join(re.sub(r"\s+", " ", str(text or "").lower()).split())


def add_message(chat_id, user_id, message_id, text, timestamp=None):
    if message_id is None:
        return False
    _HISTORY[(chat_id, user_id)].append({
        "chat_id": chat_id,
        "user_id": user_id,
        "message_id": message_id,
        "timestamp": time.time() if timestamp is None else timestamp,
        "text": _norm(text),
    })
    return True


def get_user_recent_messages(chat_id, user_id, limit=None):
    rows = list(_HISTORY.get((chat_id, user_id), ()))
    return rows[-limit:] if limit else rows


def find_spam_messages(chat_id, user_id, text=None, window=_WINDOW):
    now = time.time()
    target = _norm(text) if text is not None else None
    rows = get_user_recent_messages(chat_id, user_id)
    return [row for row in rows if now - row["timestamp"] <= window
            and (target is None or row["text"] == target)]


def clear_user_history(chat_id, user_id):
    _HISTORY.pop((chat_id, user_id), None)


def reset_all():
    _HISTORY.clear()
