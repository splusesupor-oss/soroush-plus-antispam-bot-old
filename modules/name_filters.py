"""🚫 فیلتر اسم — سیستم **مستقل** فیلتر نام کاربران، به تفکیک گروه.

این ماژول خودکفاست: ذخیره‌سازی، نرمال‌سازی، تطبیق ایموجی و تطبیق نام
همگی همین‌جا پیاده شده‌اند. هیچ import یا وابستگی‌ای به
``modules/ad_name_detector`` (سامانهٔ نام تبلیغاتی) ندارد؛ نه برای
تشخیص و نه برای ذخیره‌سازی. تنها نقطهٔ اشتراک، *اجرای مجازات* است که
عمداً از enforcement موجود ربات استفاده می‌کند تا سیستم تنبیه دوم
ساخته نشود.

دستورها::

    فیلتر اسم حسین
    فیلتر اسم 🍆
    لغو اسم حسین
    حذف فیلتر اسم حسین
    لیست فیلتر اسم

نرمال‌سازی داخلی:

* کوچک‌کردن حروف لاتین
* یکسان‌سازی «ي/ك» عربی با «ی/ک» فارسی و «ة→ه»، «أإآ→ا»
* تبدیل ارقام فارسی/عربی به لاتین
* حذف کشیده (ـ) و حرکات
* تبدیل نیم‌فاصله، نشانه‌های جهت و علائم نگارشی به فاصله
* **حفظ کامل ایموجی** تا «فیلتر اسم 🍆» واقعاً کار کند
* حذف Variation Selector (U+FE0F) و تن‌رنگ‌ها تا 🍆 و 🍆️ یکی شوند
* نسخهٔ دوم بدون حروف تکراری («حســیییین» → «حسین»)

ذخیره‌سازی در ``runtime_config_file("name_filters.json")`` با کلید
شناسهٔ نرمال‌شدهٔ گروه، پس گروه‌ها کاملاً جدا می‌مانند.
"""
import json
import re

from modules.atomic_write import write_json
from modules.group_id import normalize_group_id
from modules.runtime_paths import runtime_config_file


FILE = runtime_config_file("name_filters.json")

# دستورها
ADD_PREFIX = "فیلتر اسم"
REMOVE_PREFIXES = ("حذف فیلتر اسم", "لغو اسم")
LIST_COMMAND = "لیست فیلتر اسم"
TEST_COMMANDS = ("تست فیلتر اسم", "بررسی فیلتر اسم", "چک فیلتر اسم")
DEBUG_COMMANDS = ("دیباگ فیلتر اسم", "خام فیلتر اسم", "اطلاعات اسم")

ACTION_ADD = "add"
ACTION_REMOVE = "remove"
ACTION_LIST = "list"
ACTION_TEST = "test"
ACTION_DEBUG = "debug"

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
    "لغو اسم بعد اسم را بنویسید\n"
    "برای دیدن لیست اسم ها\n"
    "لیست فیلتر اسم"
)


# ---------------------------------------------------------------------------
# یکسان‌سازی — عیناً همان موتور فیلتر نام تبلیغاتی
# ---------------------------------------------------------------------------
# یکسان‌سازی حرف‌به‌حرف؛ عمداً جدول خودمان است و از جای دیگری نمی‌آید.
_CHAR_MAP = {
    "\u064a": "\u06cc",  # ي عربی → ی
    "\u0649": "\u06cc",  # ى
    "\u0643": "\u06a9",  # ك عربی → ک
    "\u0629": "\u0647",  # ة → ه
    "\u0623": "\u0627",  # أ → ا
    "\u0625": "\u0627",  # إ → ا
    "\u0622": "\u0627",  # آ → ا
    "\u0624": "\u0648",  # ؤ → و
    "\u0626": "\u06cc",  # ئ → ی
}
# ارقام فارسی و عربی → لاتین
for _base in ("\u06f0", "\u0660"):
    for _digit in range(10):
        _CHAR_MAP[chr(ord(_base) + _digit)] = str(_digit)

# کشیده و حرکات: کاملاً حذف می‌شوند (نه تبدیل به فاصله).
_DROP_RE = re.compile(r"[\u0640\u064b-\u065f\u0670\ufe00-\ufe0f\U0001f3fb-\U0001f3ff]")

# جداکننده‌ها → فاصله. ایموجی در این مجموعه **نیست** و دست‌نخورده می‌ماند.
_SEPARATOR_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff\u00a0\s"
    r"\-_.,/\\;:!?؟،؛|()\[\]{}<>+=*&^%$#@~\"'`«»…]+"
)

_REPEAT_RE = re.compile(r"(.)\1+")


def normalize(value):
    """نرمال‌سازی مستقل این سیستم. ایموجی حفظ می‌شود."""
    if not value:
        return ""
    text = str(value).lower()
    text = "".join(_CHAR_MAP.get(char, char) for char in text)
    text = _DROP_RE.sub("", text)
    text = _SEPARATOR_RE.sub(" ", text)
    return " ".join(text.split())


def collapse(value):
    """جمع کردن حروف تکراری: «حســیییین» → «حسین»، «🍆🍆» → «🍆»."""
    return _REPEAT_RE.sub(r"\1", str(value or ""))


def strip_spaces(value):
    """نسخهٔ بی‌فاصله — برای نامی مثل «ح س ی ن» یا «علی 🍆 خان»."""
    return str(value or "").replace(" ", "")


def is_emoji_only(value):
    """آیا عبارت فقط از ایموجی/نماد ساخته شده است؟"""
    text = normalize(value).replace(" ", "")
    if not text:
        return False
    return all(not char.isalnum() for char in text)


# ⚠️ عمداً کوتاه است. سروش برای بعضی کاربران واقعاً «ناشناخته» را
# به‌عنوان نامِ پروفایل برمی‌گرداند — این یک جای‌نگهدار نیست، نامِ خودِ
# کاربر است و باید مثل هر نام دیگری قابل فیلتر باشد. پس فقط نامِ
# واقعاً خالی «حل‌نشده» حساب می‌شود، وگرنه فیلتر «ناشناخته» هرگز
# روی کسی نمی‌خورد.
UNRESOLVED_NAMES = ()

# نام‌هایی که سروش برای کاربرانِ resolve‌نشده هم می‌فرستد. فیلترکردنشان
# مجاز است، ولی می‌تواند افرادِ کاملاً بی‌ربط را هم بگیرد، پس هنگام ثبت
# هشدار داده می‌شود.
RISKY_TERMS = (
    "ناشناخته", "نامشخص", "کاربر ناشناس", "بدون نام", "نامعلوم",
    "unknown", "no name", "deleted account",
)


def is_risky_term(term):
    """آیا این عبارت همان نامی است که سروش برای همهٔ ناشناس‌ها می‌دهد؟"""
    value = normalize(term)
    return bool(value) and value in _RISKY_KEYS


def is_unresolved(name):
    """فقط نامِ خالی. هر رشتهٔ دیگری نامِ واقعیِ قابل‌فیلتر است."""
    return not normalize(name)


def display_name(user):
    """نام نمایشی کاربر — نام + نام خانوادگی، بدون وابستگی بیرونی."""
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    return " ".join(f"{first} {last}".split())


_RISKY_KEYS = frozenset(normalize(item) for item in RISKY_TERMS)

RISKY_WARNING = (
    "⚠️ هشدار : سروش همین نام را برای کاربرانی که پروفایلشان را "
    "نمی‌دهد هم می‌فرستد، پس ممکن است افراد بی‌ربط را هم بگیرد. "
    "اگر چنین شد بنویس : لغو اسم "
)


def _keys(term):
    """کلیدهای تطبیق یک عبارت.

    سه شکل ذخیره می‌شود تا نوشتارهای مختلفِ همان نام گرفته شوند:
    شکل نرمال، شکل بدون حروف تکراری، و شکل بی‌فاصله.
    """
    normalized = normalize(term)
    if not normalized:
        return ()
    forms = [normalized, collapse(normalized), strip_spaces(normalized)]
    forms.append(collapse(strip_spaces(normalized)))
    return tuple(dict.fromkeys(form for form in forms if form))


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

    # دستورهای تشخیصی پیش از «فیلتر اسم …» دیده می‌شوند.
    for prefix in DEBUG_COMMANDS:
        if value == prefix:
            return ACTION_DEBUG, ""
        if value.startswith(prefix + " "):
            return ACTION_DEBUG, value[len(prefix) + 1:].strip()

    for prefix in TEST_COMMANDS:
        if value == prefix:
            return ACTION_TEST, ""
        if value.startswith(prefix + " "):
            return ACTION_TEST, value[len(prefix) + 1:].strip()

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
    """عبارتِ فیلترشدهٔ همین گروه که با نام کاربر می‌خورد، یا ``None``.

    تطبیق کاملاً داخلی است و هیچ موتور بیرونی‌ای صدا زده نمی‌شود.
    نام نمایشی (نام + نام خانوادگی) و یوزرنیم، هرکدام در چهار شکل
    نرمال/بی‌تکرار/بی‌فاصله بررسی می‌شوند و تطبیق «شامل‌بودن» است، پس
    «حسین» کاربرِ «حسین احمدی» را هم می‌گیرد و «🍆» کاربرِ «علی🍆» را.
    """
    entries = _entries(chat_id)
    if not entries:
        return None

    sources = (display_name(user), getattr(user, "username", None))
    candidates = []
    for source in sources:
        base = normalize(source)
        if not base:
            continue
        for form in (base, collapse(base), strip_spaces(base),
                     collapse(strip_spaces(base))):
            if form and form not in candidates:
                candidates.append(form)
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
    key = normalize_group_id(chat_id)
    if not terms:
        text = f"{EMPTY_LIST_MESSAGE}\nشناسهٔ این گروه: {key}"
        return text, []
    lines = [LIST_TITLE, ""]
    lines.extend(f"• {term}" for term in terms)
    lines.append("")
    lines.append(f"شناسهٔ این گروه: {key}")
    text = "\n".join(lines)
    return text, [("bold", 0, u16_len(LIST_TITLE))]


def build_test_message(chat_id, user, raw_name=None):
    """گزارش «تست فیلتر اسم» — چرا یک نام می‌خورد یا نمی‌خورد.

    اگر ``user`` داده شود نام نمایشی و یوزرنیم واقعی او بررسی می‌شود؛
    وگرنه ``raw_name`` به‌عنوان یک نام فرضی سنجیده می‌شود.
    """
    key = normalize_group_id(chat_id)
    terms = list_terms(chat_id)

    if user is not None:
        shown = display_name(user)
        username = (getattr(user, "username", None) or "").lstrip("@")
        matched = match_name(chat_id, user)
    else:
        shown = " ".join(str(raw_name or "").split())
        username = ""

        class _Probe:
            id = 0
            first_name = shown
            last_name = None

        matched = match_name(chat_id, _Probe)

    title = "🔎 تست فیلتر اسم"
    lines = [
        title,
        "",
        f"شناسهٔ گروه : {key}",
        f"فیلترها : {('، '.join(terms)) if terms else '— هیچ —'}",
        "",
        f"نام نمایشی : {shown or '— خالی —'}",
        f"یوزرنیم : {username or '— ندارد —'}",
        f"نام نرمال‌شده : {normalize(shown) or '— خالی —'}",
        "",
    ]
    if is_unresolved(shown):
        lines.append("⚠️ سروش برای این کاربر هیچ نامی نمی‌دهد")
        lines.append("فقط با یوزرنیم می‌شود فیلترش کرد.")
        lines.append("")

    if matched:
        lines.append(f"نتیجه : ✅ با فیلتر «{matched}» می‌خورد")
        lines.append("این کاربر با اولین پیام حذف و مجازات می‌شود.")
    elif not terms:
        lines.append("نتیجه : ❌ این گروه هیچ فیلتری ندارد")
        lines.append("فیلترها را در همین گروه ثبت کن، نه گروه دیگر.")
    else:
        lines.append("نتیجه : ❌ با هیچ فیلتری نمی‌خورد")
        suggestions = []
        if shown:
            suggestions.append(f"فیلتر اسم {shown}")
        if username:
            suggestions.append(f"فیلتر اسم {username}")
        if suggestions:
            lines.append("")
            lines.append("برای فیلتر همین کاربر یکی از این‌ها را بنویس:")
            lines.extend(suggestions)

    text = "\n".join(lines)
    return text, [("bold", 0, u16_len(title))]


def build_help_section():
    """بخش راهنمای «لیست ادمینی»: کل متن Bold داخل یک نقل‌قول شیشه‌ای."""
    length = u16_len(HELP_SECTION)
    return HELP_SECTION, [("blockquote", 0, length), ("bold", 0, length)]
