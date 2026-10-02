"""🚫 فیلتر اسم — افزودن عبارت‌های دلخواه به فیلتر نام، به تفکیک گروه.

این ماژول **سیستم جدیدی نمی‌سازد**. فقط فهرست عبارت‌های دلخواهِ هر
گروه را نگه می‌دارد و تشخیص را به ``modules/ad_name_detector`` تحویل
می‌دهد: همان نرمال‌سازی (حذف نیم‌فاصله، کشیده، حرکات، علائم، یکسان‌سازی
ی/ک عربی) و همان جمع‌کردن حروف تکراری استفاده می‌شود، پس «حســیــن» و
«حسییییین» هم گرفته می‌شوند.

مجازات هم همان مجازات نام تبلیغاتی فعلی است؛ اینجا هیچ enforcement
جداگانه‌ای وجود ندارد. ``ad_name_detector.reason(user, chat_id)`` بعد
از الگوهای داخلی، فهرست همین ماژول را هم بررسی می‌کند و خروجی‌اش به
همان مسیر موجود در ``handlers/message_handler`` می‌رسد.

ایموجی هم پشتیبانی می‌شود: نرمال‌سازی ad_name_detector ایموجی را حذف
نمی‌کند، پس «فیلتر اسم 🍆» دقیقاً همان ایموجی را فیلتر می‌کند.

ذخیره‌سازی در ``runtime_config_file("name_filters.json")`` است و کلید
هر رکورد شناسهٔ نرمال‌شدهٔ گروه، پس گروه‌ها کاملاً جدا می‌مانند و
نمونه‌های مختلف ربات (BOT_INSTANCE) داده‌هایشان قاطی نمی‌شود.
"""
import json

from modules import ad_name_detector
from modules.atomic_write import write_json
from modules.group_id import normalize_group_id
from modules.runtime_paths import runtime_config_file


FILE = runtime_config_file("name_filters.json")

# دستورها
ADD_PREFIX = "فیلتر اسم"
REMOVE_PREFIXES = ("حذف فیلتر اسم", "لغو اسم")
LIST_COMMAND = "لیست فیلتر اسم"

ACTION_ADD = "add"
ACTION_REMOVE = "remove"
ACTION_LIST = "list"

# سقف‌ها: جلوی رشد بی‌پایان فایل و عبارت‌های بی‌معنی را می‌گیرد.
MAX_TERMS_PER_GROUP = 200
MAX_TERM_LENGTH = 64

# پیام‌ها
DENIED_MESSAGE = (
    "❌ فقط مالک ثبت‌شده و ادمین ثبت‌شدهٔ گروه اجازهٔ استفاده از فیلتر اسم را دارند"
)
EMPTY_TERM_MESSAGE = "❌ عبارت فیلتر را بعد از دستور بنویسید."
TOO_LONG_MESSAGE = "❌ این عبارت برای فیلتر اسم خیلی طولانی است."
LIMIT_MESSAGE = "❌ ظرفیت فیلتر اسم این گروه پر شده است."
ALREADY_MESSAGE = "ℹ️ این عبارت از قبل در فیلتر اسم گروه هست."
NOT_FOUND_MESSAGE = "❌ این عبارت در فیلتر اسم گروه پیدا نشد."
EMPTY_LIST_MESSAGE = "📭 فیلتر اسمی برای این گروه ثبت نشده است."
LIST_TITLE = "🚫 لیست فیلتر اسم گروه"

# متن بخش راهنمای «لیست ادمینی» — بدون خط خالی بین جمله‌ها.
HELP_SECTION = (
    "برای فیلتر اسم یک کاربر\n"
    "بنویسید فیلتر اسم بعد نام را بنویسید\n"
    "برای لغو بنویسید\n"
    "لغو اسم بعد اسم را بنویسید"
)


# ---------------------------------------------------------------------------
# یکسان‌سازی — عیناً همان موتور فیلتر نام تبلیغاتی
# ---------------------------------------------------------------------------
def normalize(value):
    """نرمال‌سازی مشترک با ``ad_name_detector``."""
    return ad_name_detector._norm(value)


def collapse(value):
    """جمع کردن حروف تکراری، مثل همان ماژول."""
    return ad_name_detector._collapse(value)


def _keys(term):
    """کلیدهای تطبیق یک عبارت: شکل عادی و شکل بدون حروف تکراری."""
    normalized = normalize(term)
    if not normalized:
        return ()
    collapsed = collapse(normalized)
    return tuple(dict.fromkeys((normalized, collapsed)))


def u16_len(value):
    return len(str(value or "").encode("utf-16-le")) // 2


# ---------------------------------------------------------------------------
# تطبیق دستور
# ---------------------------------------------------------------------------
_NORMALIZE_COMMAND = {
    "\u200c": " ",
    "\u200f": "",
    "\u200e": "",
    "\ufeff": "",
    "\u064a": "\u06cc",
    "\u0643": "\u06a9",
}


def normalize_command(text):
    value = str(text or "")
    for source, target in _NORMALIZE_COMMAND.items():
        value = value.replace(source, target)
    return " ".join(value.split())


def match_command(text):
    """``(action, term)`` یا ``None``.

    ترتیب بررسی مهم است: «حذف فیلتر اسم …» و «لیست فیلتر اسم» پیش از
    «فیلتر اسم …» دیده می‌شوند تا هیچ‌کدام دیگری را نبلعد.
    """
    value = normalize_command(text)
    if not value:
        return None

    if value == LIST_COMMAND:
        return ACTION_LIST, None

    for prefix in REMOVE_PREFIXES:
        if value == prefix:
            return ACTION_REMOVE, ""
        if value.startswith(prefix + " "):
            return ACTION_REMOVE, value[len(prefix) + 1:].strip()

    if value == ADD_PREFIX:
        return ACTION_ADD, ""
    if value.startswith(ADD_PREFIX + " "):
        return ACTION_ADD, value[len(ADD_PREFIX) + 1:].strip()

    return None


# ---------------------------------------------------------------------------
# ذخیره‌سازی
# ---------------------------------------------------------------------------
_cache = None
_cache_mtime = None


def _file_mtime():
    try:
        return FILE.stat().st_mtime_ns
    except OSError:
        return None


def _load():
    global _cache, _cache_mtime
    mtime = _file_mtime()
    if _cache is not None and mtime == _cache_mtime:
        return _cache
    if mtime is None:
        _cache = {}
    else:
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
            _cache = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _cache = {}
    _cache_mtime = mtime
    return _cache


def _save(data):
    global _cache, _cache_mtime
    write_json(FILE, data, indent=2)
    _cache = data
    _cache_mtime = _file_mtime()


def reset_cache():
    """برای تست‌ها."""
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None


def _entries(chat_id):
    raw = _load().get(normalize_group_id(chat_id), [])
    return [item for item in raw if isinstance(item, dict) and item.get("term")]


def list_terms(chat_id):
    """عبارت‌های ثبت‌شدهٔ همین گروه، به شکلی که ادمین نوشته است."""
    return [str(item["term"]) for item in _entries(chat_id)]


def has_term(chat_id, term):
    keys = set(_keys(term))
    if not keys:
        return False
    for item in _entries(chat_id):
        if keys & set(item.get("keys") or ()):
            return True
    return False


def add(chat_id, term, user_id=None):
    """``(ok, message, display)`` — عبارت را به فیلتر همین گروه اضافه می‌کند."""
    display = " ".join(str(term or "").split())
    if not display:
        return False, EMPTY_TERM_MESSAGE, ""
    if len(display) > MAX_TERM_LENGTH:
        return False, TOO_LONG_MESSAGE, display
    keys = _keys(display)
    if not keys:
        # عبارتی که بعد از نرمال‌سازی چیزی از آن نمی‌ماند (فقط علائم)
        # هرگز نباید ذخیره شود؛ وگرنه با هر نامی تطبیق می‌کرد.
        return False, EMPTY_TERM_MESSAGE, display

    data = dict(_load())
    key = normalize_group_id(chat_id)
    items = list(_entries(key))
    for item in items:
        if set(keys) & set(item.get("keys") or ()):
            return False, ALREADY_MESSAGE, str(item.get("term") or display)
    if len(items) >= MAX_TERMS_PER_GROUP:
        return False, LIMIT_MESSAGE, display

    record = {"term": display, "keys": list(keys)}
    if user_id is not None:
        record["added_by"] = int(user_id)
    items.append(record)
    data[key] = items
    _save(data)
    return True, None, display


def remove(chat_id, term):
    """``(ok, message, display)`` — فقط همان یک عبارت را حذف می‌کند."""
    display = " ".join(str(term or "").split())
    if not display:
        return False, EMPTY_TERM_MESSAGE, ""
    keys = set(_keys(display))
    if not keys:
        return False, NOT_FOUND_MESSAGE, display

    data = dict(_load())
    key = normalize_group_id(chat_id)
    items = list(_entries(key))
    kept = []
    removed = None
    for item in items:
        if removed is None and keys & set(item.get("keys") or ()):
            removed = str(item.get("term") or display)
            continue
        kept.append(item)
    if removed is None:
        return False, NOT_FOUND_MESSAGE, display
    data[key] = kept
    _save(data)
    return True, None, removed


def clear(chat_id):
    data = dict(_load())
    data[normalize_group_id(chat_id)] = []
    _save(data)
    return True


# ---------------------------------------------------------------------------
# تطبیق نام کاربر
# ---------------------------------------------------------------------------
def match_name(chat_id, user):
    """اگر نام نمایشی/یوزرنیم کاربر با فیلتری از همین گروه بخورد، همان را برمی‌گرداند."""
    entries = _entries(chat_id)
    if not entries:
        return None

    username = normalize(getattr(user, "username", None))
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    name = normalize(f"{first} {last}".strip())

    candidates = []
    for value in (username, name):
        if not value:
            continue
        candidates.append(value)
        collapsed = collapse(value)
        if collapsed != value:
            candidates.append(collapsed)
    if not candidates:
        return None

    for item in entries:
        for key in item.get("keys") or ():
            if not key:
                continue
            for candidate in candidates:
                if key in candidate:
                    return str(item.get("term") or key)
    return None


# ---------------------------------------------------------------------------
# پیام‌های خروجی — Bold داخل نقل‌قول شیشه‌ای
# ---------------------------------------------------------------------------
def build_added_message(display):
    text = f"نام : {display} فیلتر شد"
    length = u16_len(text)
    return text, [("blockquote", 0, length), ("bold", 0, length)]


def build_removed_message(display):
    text = f"نام : {display} از فیلتر خارج شد"
    length = u16_len(text)
    return text, [("blockquote", 0, length), ("bold", 0, length)]


def build_list_message(chat_id):
    terms = list_terms(chat_id)
    if not terms:
        return EMPTY_LIST_MESSAGE, []
    lines = [LIST_TITLE, ""]
    lines.extend(f"• {term}" for term in terms)
    text = "\n".join(lines)
    return text, [("bold", 0, u16_len(LIST_TITLE))]


def build_help_section():
    """بخش راهنمای «لیست ادمینی»: کل متن Bold داخل یک نقل‌قول شیشه‌ای."""
    length = u16_len(HELP_SECTION)
    return HELP_SECTION, [("blockquote", 0, length), ("bold", 0, length)]
