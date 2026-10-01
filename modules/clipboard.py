"""📮 کپی بورد (حافظهٔ روباهی) — ذخیرهٔ یک پیام آماده برای هر گروه.

منطق قابلیت
-----------
* دستور «کپی بورد» فقط *حالت ذخیره* را باز می‌کند و پیام راهنما را
  نشان می‌دهد؛ هیچ متنی ارسال نمی‌کند.
* ذخیره **فقط** با Reply روی همان پیام راهنما انجام می‌شود.
* دستور «کپی» متن ذخیره‌شده را با همان قالب‌بندی ارسال می‌کند.

قالب‌بندی
---------
در سروش پلاس (مثل Telethon) استایل پیام در ``message.entities`` است،
نه در متن. پس موقع ذخیره، entityهای پیام کاربر گرفته و در کنار متن
نگه داشته می‌شوند و موقع «کپی» دوباره با ``formatting_entities=`` پس
داده می‌شوند. هیچ Markdown ساختگی‌ای تولید نمی‌شود.

ماندگاری و جداسازی
------------------
داده در ``runtime_config_file("clipboard.json")`` ذخیره می‌شود. این
مسیر از ``modules/runtime_paths`` می‌آید و بر اساس ``BOT_INSTANCE``
جداست، پس Bot1/Bot2/Bot3 هرگز کپی‌بورد هم را نمی‌بینند. کلید هر رکورد
شناسهٔ نرمال‌شدهٔ گروه است، پس گروه A و گروه B کاملاً جدا می‌مانند.
"""
import json
import time

from modules.atomic_write import write_json
from modules.group_id import normalize_group_id
from modules.runtime_paths import runtime_config_file


FILE = runtime_config_file("clipboard.json")

# دستورها — تطبیق «دقیق» است تا هیچ مسیر دیگری را نگیرند.
SAVE_COMMAND = "کپی بورد"
SHOW_COMMAND = "کپی"

MODE_SAVE = "save"
MODE_SHOW = "show"

# سقف طول متن بر حسب واحد UTF-16 (همان واحدی که offset entity با آن
# شمرده می‌شود و همان سقف عملی پیام در سروش پلاس).
MAX_TEXT_UNITS = 4096

# چند پیام راهنمای آخر هر گروه معتبر می‌مانند تا اگر ادمین دو بار
# «کپی بورد» زد، Reply روی راهنمای قبلی هم کار کند.
MAX_HELP_MESSAGES = 10


# ---------------------------------------------------------------------------
# متن راهنما — عیناً طبق درخواست.
# ---------------------------------------------------------------------------
HELP_TITLE = "🔖راهنما و توضیحات کپی بورد"
HELP_BODY = (
    "قابلیت کپی بورد به این صورت می‌باشد که میتوانید یک متن به هم به صورت "
    "ساده و هم ب صورت bold شده و یا نقل قول شده به ربات بدهید و بعدا با "
    "دستور کپی بورد اون متن رو ارسال میکنه اما چه استفاده ای می‌تونه داشته "
    "باشه مثلا در مواردی مثل وقتی که گروه میبندید میخایین بعد از قفل شدن "
    "لینکی رو برای سین زدن یا برای دیده شدن فواورد کنید ربات مستقیم نشان "
    "میده یا موقع چت گروهی میتوانید بدون نیاز به فواورد از کانالی یا پیام "
    "شخصی لینک کانال گروه دوم یا پیوی خصوصی و یا تکست و اعلان های مهم گروه "
    "رو با هر شکل و توضیحی به ربات بدهید و با همون دستور ربات سریع نمایش "
    "خواهد داد"
)
HELP_FOOTER = (
    "📌روی همین پیام ریپلای کنید و متن یا تکست و لینک خودتون رو بفرستید"
)

# پیام‌های کوتاه
SAVED_MESSAGE = "✅ متن کپی بورد با موفقیت ذخیره شد."
EMPTY_MESSAGE = "❌ هنوز متنی برای کپی ذخیره نشده است."
INVALID_MESSAGE = "❌ متن معتبری برای ذخیره در کپی بورد پیدا نشد."
TOO_LONG_MESSAGE = (
    "❌ این متن طولانی‌تر از حد مجاز سروش پلاس است و قابل ذخیره نیست."
)
DENIED_MESSAGE = (
    "❌ فقط مالک ثبت‌شده و ادمین‌های ربات اجازهٔ استفاده از کپی بورد را دارند"
)

# متن بخش راهنمای «لیست ادمینی».
HELP_SECTION = (
    "📮کپی بورد حافظه روباهی\n"
    "برای ایجاد بنویسید کپی بورد\n"
    "برای نمایش پیام بنویس کپی"
)


# ---------------------------------------------------------------------------
# یکسان‌سازی و تطبیق دستور
# ---------------------------------------------------------------------------
_NORMALIZE = {
    "\u200c": " ",   # نیم‌فاصله
    "\u200f": "",    # RTL mark
    "\u200e": "",    # LTR mark
    "\ufeff": "",
    "\u064a": "\u06cc",  # ي عربی
    "\u0643": "\u06a9",  # ك عربی
}


def normalize_command(text):
    value = str(text or "")
    for source, target in _NORMALIZE.items():
        value = value.replace(source, target)
    return " ".join(value.split())


def match_command(text):
    """``"save"`` برای «کپی بورد»، ``"show"`` برای «کپی»، وگرنه ``None``.

    تطبیق کامل است: «کپی بورد گروه»، «کپی کن» یا «کپی ۱۰» هیچ‌کدام
    تطبیق نمی‌کنند، پس این مسیر با هیچ دستور دیگری تداخل ندارد.
    """
    normalized = normalize_command(text)
    if normalized == SAVE_COMMAND:
        return MODE_SAVE
    if normalized == SHOW_COMMAND:
        return MODE_SHOW
    return None


def u16_len(value):
    """طول بر حسب واحد UTF-16 — همان واحد offset در entityها."""
    return len(str(value or "").encode("utf-16-le")) // 2


# ---------------------------------------------------------------------------
# متن راهنما + spanهای قالب‌بندی
# ---------------------------------------------------------------------------
def build_help_message():
    """``(text, spans)``؛ span یعنی ``(kind, offset, length)``.

    * عنوان: هم Bold و هم داخل نقل‌قول سروش پلاس
    * متن توضیحات: Bold
    * خط پایانی: ساده
    """
    text = f"{HELP_TITLE}\n\n{HELP_BODY}\n\n{HELP_FOOTER}"
    title_offset = 0
    title_length = u16_len(HELP_TITLE)
    body_offset = title_length + 2  # دو «\n»
    body_length = u16_len(HELP_BODY)
    spans = [
        ("blockquote", title_offset, title_length),
        ("bold", title_offset, title_length),
        ("bold", body_offset, body_length),
    ]
    return text, spans


def build_help_section():
    """بخش «کپی بورد» برای راهنمای لیست ادمینی: کل متن Bold داخل نقل‌قول."""
    length = u16_len(HELP_SECTION)
    return HELP_SECTION, [("blockquote", 0, length), ("bold", 0, length)]


# ---------------------------------------------------------------------------
# سریال‌سازی entity
#
# entityها شیء API هستند و مستقیماً JSON نمی‌شوند. فقط فیلدهای سادهٔ
# هر entity ذخیره و موقع خواندن دوباره همان کلاس ساخته می‌شود، پس
# Bold/Quote/لینک/منشن بعد از ری‌استارت هم سالم می‌مانند.
# ---------------------------------------------------------------------------
_PRIMITIVES = (str, int, float, bool, type(None))


class _FallbackEntity:
    """جایگزین وقتی splusthon نصب نیست (محیط تست/CI)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):  # pragma: no cover - فقط برای خطایابی
        return f"{type(self).__name__}({self.__dict__})"

    def __eq__(self, other):
        return (type(self).__name__ == type(other).__name__
                and getattr(other, "__dict__", None) == self.__dict__)


_FALLBACK_CACHE = {}


def _entity_class(name):
    try:
        from splusthon.tl import types as _types
        found = getattr(_types, name, None)
        if found is not None:
            return found
    except Exception:
        pass
    if name not in _FALLBACK_CACHE:
        _FALLBACK_CACHE[name] = type(name, (_FallbackEntity,), {})
    return _FALLBACK_CACHE[name]


def serialize_entities(entities):
    """entityهای API را به ساختار JSON‌پذیر تبدیل می‌کند."""
    result = []
    for entity in entities or []:
        name = type(entity).__name__
        if not name.startswith("MessageEntity"):
            # Input*MentionName و امثال آن شیء پیچیده دارند و ماندگار
            # نمی‌شوند؛ بی‌صدا رد می‌شوند تا بقیهٔ قالب حفظ شود.
            continue
        source = getattr(entity, "__dict__", None) or {}
        data = {}
        usable = True
        for key, value in source.items():
            if key.startswith("_"):
                continue
            if isinstance(value, _PRIMITIVES):
                data[key] = value
            else:
                usable = False
                break
        if not usable:
            continue
        if "offset" not in data or "length" not in data:
            continue
        data["type"] = name
        result.append(data)
    return result


def deserialize_entities(items):
    """ساختار ذخیره‌شده را دوباره به entity واقعی تبدیل می‌کند."""
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = item.get("type")
        if not name:
            continue
        kwargs = {k: v for k, v in item.items() if k != "type"}
        cls = _entity_class(name)
        try:
            result.append(cls(**kwargs))
        except TypeError:
            # نسخهٔ کتابخانه فیلد اضافه‌ای را نمی‌شناسد: با حداقل‌ها بساز.
            try:
                result.append(cls(offset=kwargs.get("offset", 0),
                                  length=kwargs.get("length", 0)))
            except Exception:
                continue
        except Exception:
            continue
    return result


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


def _record(data, chat_id):
    record = data.get(normalize_group_id(chat_id))
    return record if isinstance(record, dict) else {}


def reset_cache():
    """برای تست‌ها: کش را دور می‌ریزد تا فایل تازه خوانده شود."""
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None


# --- حالت ذخیره (پیام راهنما) -------------------------------------------
def open_save_mode(chat_id, help_message_id):
    """شناسهٔ پیام راهنما را ثبت می‌کند تا Reply روی آن معتبر باشد."""
    if help_message_id is None:
        return False
    data = dict(_load())
    key = normalize_group_id(chat_id)
    record = dict(_record(data, key))
    pending = [int(x) for x in record.get("help_message_ids", [])
               if isinstance(x, int) or str(x).lstrip("-").isdigit()]
    value = int(help_message_id)
    if value in pending:
        pending.remove(value)
    pending.append(value)
    record["help_message_ids"] = pending[-MAX_HELP_MESSAGES:]
    data[key] = record
    _save(data)
    return True


def is_help_message(chat_id, message_id):
    """آیا این شناسه یکی از پیام‌های راهنمای همین گروه است."""
    if message_id is None:
        return False
    try:
        value = int(message_id)
    except (TypeError, ValueError):
        return False
    return value in [int(x) for x in
                     _record(_load(), chat_id).get("help_message_ids", [])]


# --- خود کپی‌بورد ---------------------------------------------------------
def save(chat_id, text, entities=None, user_id=None):
    """متن جدید را جایگزین کپی‌بورد همان گروه می‌کند."""
    data = dict(_load())
    key = normalize_group_id(chat_id)
    record = dict(_record(data, key))
    record["text"] = str(text)
    record["entities"] = serialize_entities(entities)
    record["saved_at"] = int(time.time())
    if user_id is not None:
        record["saved_by"] = int(user_id)
    data[key] = record
    _save(data)
    return True


def get(chat_id):
    """``(text, entities)`` یا ``(None, [])`` اگر چیزی ذخیره نشده باشد."""
    record = _record(_load(), chat_id)
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, []
    return text, deserialize_entities(record.get("entities"))


def has_clipboard(chat_id):
    text, _entities = get(chat_id)
    return text is not None


def clear(chat_id):
    data = dict(_load())
    key = normalize_group_id(chat_id)
    record = dict(_record(data, key))
    record.pop("text", None)
    record.pop("entities", None)
    record.pop("saved_at", None)
    record.pop("saved_by", None)
    data[key] = record
    _save(data)
    return True


# ---------------------------------------------------------------------------
# اعتبارسنجی متنِ ورودی
# ---------------------------------------------------------------------------
def validate(text):
    """``(ok, message)`` — طول و محتوای متن را پیش از ذخیره بررسی می‌کند."""
    value = str(text or "")
    if not value.strip():
        return False, INVALID_MESSAGE
    if u16_len(value) > MAX_TEXT_UNITS:
        return False, TOO_LONG_MESSAGE
    from modules import content_guard
    ok, message = content_guard.check(value)
    if not ok:
        return False, message
    return True, None
