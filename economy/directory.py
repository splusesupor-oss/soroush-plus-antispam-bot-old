"""📇 دفترچهٔ یوزرنیم → شناسهٔ کاربر، به تفکیک گروه.

انتقال سکه با یوزرنیم انجام می‌شود، پس باید بتوانیم «@username» را به
شناسهٔ عددی تبدیل کنیم. هر بار کاربری در گروه پیام می‌دهد، یوزرنیمش
اینجا ثبت می‌شود.

هر گروه دفترچهٔ خودش را دارد، دقیقاً مثل کیف پول؛ پس یوزرنیم یکسان در
دو گروه با دو حساب متفاوت قاطی نمی‌شود.

داده‌ها زیر کلید ``usernames`` در همان فایل اقتصاد می‌نشینند.
"""
from economy import storage
from economy.coins import accounts


def normalize(username):
    """``"@Ali "`` → ``"ali"``؛ ``None`` اگر یوزرنیم معتبر نباشد."""
    if username is None:
        return None
    value = str(username).strip()
    for junk in ("\u200c", "\u200f", "\u200e"):
        value = value.replace(junk, "")
    value = value.strip().lstrip("@").strip().lower()
    return value or None


def is_valid(username):
    """آیا این متن یک یوزرنیم است (نه شناسهٔ عددی، نه متن دلخواه).

    قواعد سروش پلاس مثل تلگرام است: حروف انگلیسی، رقم و زیرخط، و باید
    با حرف شروع شود. شناسهٔ عددی عمداً رد می‌شود.
    """
    value = normalize(username)
    if not value or len(value) < 3 or len(value) > 32:
        return False
    if value.isdigit():
        return False
    if not (value[0].isalpha() and value[0].isascii()):
        return False
    return all((char.isascii() and (char.isalnum() or char == "_"))
               for char in value)


def remember(chat_id, user_id, username):
    """یوزرنیم این کاربر را در دفترچهٔ همین گروه ثبت می‌کند."""
    key = normalize(username)
    if not key or user_id is None:
        return None
    chat = accounts.chat_key(chat_id)
    with storage.transaction(defer=True) as data:
        book = data.setdefault("usernames", {}).setdefault(chat, {})
        if book.get(key) == str(user_id):
            return str(user_id)
        book[key] = str(user_id)
        return str(user_id)


def lookup(chat_id, username):
    """شناسهٔ کاربر با این یوزرنیم در همین گروه، یا ``None``."""
    key = normalize(username)
    if not key:
        return None
    chat = accounts.chat_key(chat_id)
    data = storage.snapshot()
    found = data.get("usernames", {}).get(chat, {}).get(key)
    return str(found) if found is not None else None


def username_of(chat_id, user_id):
    """یوزرنیم ثبت‌شدهٔ یک کاربر در این گروه، یا ``None``."""
    chat = accounts.chat_key(chat_id)
    book = storage.snapshot().get("usernames", {}).get(chat, {})
    target = str(user_id)
    for name, stored in book.items():
        if str(stored) == target:
            return name
    return None


def forget(chat_id, username):
    key = normalize(username)
    if not key:
        return False
    chat = accounts.chat_key(chat_id)
    with storage.transaction() as data:
        book = data.setdefault("usernames", {}).setdefault(chat, {})
        return book.pop(key, None) is not None


def entries(chat_id):
    """کپی فقط-خواندنی از دفترچهٔ این گروه."""
    chat = accounts.chat_key(chat_id)
    return dict(storage.snapshot().get("usernames", {}).get(chat, {}))
