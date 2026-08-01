"""💾 پیشرفت دائمی بازی‌ها، به تفکیک گروه و کاربر.

پیش‌تر پیشرفت «حدس ایموجی» فقط در یک dict داخل حافظه بود، پس با هر
ری‌استارت، کرش یا آپدیت از بین می‌رفت و کاربر دوباره از مرحلهٔ ۱ شروع
می‌کرد.

اینجا پیشرفت داخل همان فایل اقتصاد (``config/economy.json``) نگه داشته
می‌شود، زیر کلید ``game_progress``:

    game_progress
      └── "<chat_key>"
            └── "<user_id>"
                  └── "<game>"
                        └── ["پاسخ۱", "پاسخ۲", ...]

هر گروه دفتر جدا دارد، دقیقاً مثل کیف پول؛ پس پیشرفت یک کاربر در یک
گروه روی گروه دیگر اثر نمی‌گذارد.

نوشتن با ``defer=True`` انجام می‌شود تا مسیر داغ کند نشود؛ حلقهٔ دوره‌ای
ربات آن را روی دیسک می‌نشاند. برای اطمینان، ``mark_seen`` بلافاصله هم
flush می‌کند چون از دست رفتن یک مرحله برای کاربر آزاردهنده است.
"""
from economy import storage
from economy.coins import accounts

ROOT = "game_progress"
RECENT = "game_recent"
CYCLE_KEY = "__cycle__"


def _chat(chat_id):
    return accounts.chat_key(chat_id)


def _bucket(data, chat_id, user_id, game, *, create=False):
    root = data.setdefault(ROOT, {}) if create else data.get(ROOT, {})
    chat = root.setdefault(_chat(chat_id), {}) if create \
        else root.get(_chat(chat_id), {})
    user = chat.setdefault(str(user_id), {}) if create \
        else chat.get(str(user_id), {})
    if create:
        return user.setdefault(game, [])
    return user.get(game, [])


def seen(chat_id, user_id, game):
    """مجموعهٔ مرحله‌هایی که این کاربر در این گروه دیده است."""
    data = storage.snapshot()
    return {str(item) for item in _bucket(data, chat_id, user_id, game)}


def seen_count(chat_id, user_id, game):
    return len(seen(chat_id, user_id, game))


def has_seen(chat_id, user_id, game, item):
    return str(item) in seen(chat_id, user_id, game)


def mark_seen(chat_id, user_id, game, item):
    """یک مرحله را «دیده‌شده» ثبت می‌کند و روی دیسک می‌نشاند.

    خروجی: تعداد کل مرحله‌های دیده‌شده پس از ثبت.
    """
    value = str(item)
    with storage.transaction(defer=True) as data:
        bucket = _bucket(data, chat_id, user_id, game, create=True)
        if value not in bucket:
            bucket.append(value)
        total = len(bucket)
    # پیشرفت نباید با یک کرش از دست برود.
    try:
        storage.flush()
    except Exception:
        pass
    return total


def reset(chat_id, user_id, game):
    """پیشرفت این کاربر در این بازی و همین گروه را پاک می‌کند."""
    with storage.transaction() as data:
        root = data.get(ROOT, {})
        chat = root.get(_chat(chat_id), {})
        user = chat.get(str(user_id), {})
        had = bool(user.get(game))
        user.pop(game, None)
        if not user:
            chat.pop(str(user_id), None)
        if not chat:
            root.pop(_chat(chat_id), None)
        return had


def reset_game_everywhere(game):
    """پیشرفت یک بازی را برای همهٔ کاربران پاک می‌کند — فقط برای تست.

    فهرست «تازه‌مصرف‌شدهٔ» گروه‌ها هم پاک می‌شود؛ در غیر این صورت یک
    پنجرهٔ کهنه باقی می‌ماند و انتخاب معما را بی‌دلیل محدود می‌کند.
    """
    with storage.transaction() as data:
        root = data.get(ROOT, {})
        for chat in list(root.values()):
            for user in list(chat.values()):
                user.pop(game, None)
                user.pop(f"{game}{CYCLE_KEY}", None)
        for chat in list(data.get(RECENT, {}).values()):
            chat.pop(game, None)


# ---------------------------------------------------------------------------
# مرحله‌های «تازه استفاده‌شده» در کل گروه
#
# بدون این، کاربر تازه‌وارد ممکن بود همان معمایی را بگیرد که چند لحظه
# پیش کاربر دیگری در همان گروه جواب داده بود، پس بقیه جواب را می‌دانستند.
# ---------------------------------------------------------------------------
def recent(chat_id, game):
    data = storage.snapshot()
    bucket = data.get(RECENT, {}).get(_chat(chat_id), {}).get(game, [])
    return [str(item) for item in bucket]


def mark_recent(chat_id, game, item, limit):
    """مرحله را در فهرست «تازه استفاده‌شدهٔ گروه» ثبت می‌کند.

    فهرست کوتاه نگه داشته می‌شود (``limit``) تا با مصرف شدن بانک، بازی
    قفل نشود.
    """
    value = str(item)
    with storage.transaction(defer=True) as data:
        chat = data.setdefault(RECENT, {}).setdefault(_chat(chat_id), {})
        bucket = chat.setdefault(game, [])
        if value in bucket:
            bucket.remove(value)
        bucket.append(value)
        if limit > 0 and len(bucket) > limit:
            del bucket[:-limit]
        size = len(bucket)
    try:
        storage.flush()
    except Exception:
        pass
    return size


def clear_recent(chat_id, game):
    with storage.transaction() as data:
        chat = data.get(RECENT, {}).get(_chat(chat_id), {})
        chat.pop(game, None)


# ---------------------------------------------------------------------------
# دور (cycle): وقتی کاربر همهٔ مرحله‌ها را دید، دور تازه شروع می‌شود
# ---------------------------------------------------------------------------
def cycle(chat_id, user_id, game):
    data = storage.snapshot()
    user = data.get(ROOT, {}).get(_chat(chat_id), {}).get(str(user_id), {})
    return int(user.get(f"{game}{CYCLE_KEY}", 0) or 0)


def start_new_cycle(chat_id, user_id, game):
    """تاریخچهٔ کاربر را خالی و شمارندهٔ دور را یکی زیاد می‌کند."""
    with storage.transaction() as data:
        root = data.setdefault(ROOT, {})
        chat = root.setdefault(_chat(chat_id), {})
        user = chat.setdefault(str(user_id), {})
        user[game] = []
        current = int(user.get(f"{game}{CYCLE_KEY}", 0) or 0) + 1
        user[f"{game}{CYCLE_KEY}"] = current
    try:
        storage.flush()
    except Exception:
        pass
    return current


def all_users(chat_id, game):
    """کاربران این گروه که در این بازی پیشرفتی دارند."""
    data = storage.snapshot()
    chat = data.get(ROOT, {}).get(_chat(chat_id), {})
    return {user_id: len(games.get(game, []))
            for user_id, games in chat.items() if games.get(game)}
