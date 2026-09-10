"""کنترل سرگرمی به تفکیک گروه — دستورهای «سرگرمی خاموش» / «سرگرمی فعال».

پیش‌فرض هر گروه «فعال» است؛ فقط مالک اصلی ربات، مالک ثبت‌شدهٔ گروه یا
ادمینِ ثبت‌شدهٔ همان گروه می‌تواند وضعیت را عوض کند.

وضعیت در ``config/entertainment_mode.json`` ذخیره می‌شود. مسیر از
``modules.runtime_paths.runtime_config_file`` گرفته می‌شود، پس هر instance
(BOT_INSTANCE) فایل مستقل خودش را دارد و instanceها روی هم اثر نمی‌گذارند.
نوشتن اتمیک است (``modules.atomic_write``) و خواندن با کش mtime، دقیقاً مثل
سایر سوییچ‌های per-group ربات؛ هیچ دادهٔ قبلی (سکه، امتیاز، ادمین، تنظیمات)
لمس نمی‌شود چون این کلید در فایل جداگانهٔ خودش زندگی می‌کند.

این ماژول فقط سرگرمی‌های داخل خود ربات را کنترل می‌کند؛ سایت بازی
(Fox Game Center) و ماژول‌های آن اصلاً از این مسیر عبور نمی‌کنند.
"""
from __future__ import annotations

import json
import os

from modules.atomic_write import write_json
from modules.group_id import normalize_group_id
from modules.runtime_paths import runtime_config_file

FILE = runtime_config_file("entertainment_mode.json")

# ----------------------------- پیام‌های ثابت -----------------------------
# متن‌ها عیناً همان چیزی هستند که باید ارسال شوند؛ هیچ کاراکتری اضافه/کم نشود.
DISABLED_NOTICE = "🎮 بازی های روباه غیر فعال شد"
ENABLED_NOTICE = (
    "🍬 : بازی های روباه فعال شد میتوانید با دستور لیست بازی از بازی ها "
    "استفاده کنید"
)
BLOCKED_NOTICE = (
    "بازی های روباه عموم غیر فعال می‌باشند ؛ برای فعال سازی باید ادمین یا "
    "مالک با دستور سرگرمی فعال بازی هارو فعال کند تا بتوانید از بازی ها "
    "استفاده کنید ☑️"
)
# فقط همین عبارت داخل پیام بالا Bold می‌شود.
BLOCKED_BOLD_PART = "سرگرمی فعال"

PERMISSION_DENIED = "❌ فقط مالک یا ادمین‌های گروه اجازه تغییر وضعیت سرگرمی را دارند"

COMMAND_DISABLE = "سرگرمی خاموش"
COMMAND_ENABLE = "سرگرمی فعال"
COMMANDS = frozenset({COMMAND_DISABLE, COMMAND_ENABLE})

_cache = None
_cache_mtime = None


def _file_mtime():
    try:
        return os.stat(FILE).st_mtime_ns
    except OSError:
        return None


def _key(chat_id):
    return str(normalize_group_id(chat_id))


def load():
    """محتوای فایل با کش mtime؛ فایل غایب/خراب → دیکشنری خالی."""
    global _cache, _cache_mtime
    mtime = _file_mtime()
    if _cache is not None and mtime == _cache_mtime:
        return _cache
    if mtime is None:
        _cache = {}
    else:
        try:
            with open(FILE, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            _cache = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _cache = {}
    _cache_mtime = mtime
    return _cache


def save(data):
    global _cache, _cache_mtime
    write_json(FILE, data, indent=2)
    _cache = data
    _cache_mtime = _file_mtime()


def is_enabled(chat_id):
    """آیا سرگرمی این گروه فعال است؟ پیش‌فرض (بدون تنظیم) فعال است."""
    try:
        return bool(load().get(_key(chat_id), True))
    except Exception:
        # هیچ خطای storage نباید بازی‌ها را برای همیشه ببندد؛ پیش‌فرض فعال.
        return True


def set_enabled(chat_id, enabled):
    data = dict(load())
    data[_key(chat_id)] = bool(enabled)
    save(data)
    return bool(enabled)


def enable(chat_id):
    return set_enabled(chat_id, True)


def disable(chat_id):
    return set_enabled(chat_id, False)


def reset(chat_id):
    """برگرداندن گروه به حالت پیش‌فرض (فعال) با حذف کلید آن."""
    data = dict(load())
    if data.pop(_key(chat_id), None) is not None:
        save(data)
    return True


# ------------------------------ Bold واقعی ------------------------------
def u16_length(text):
    """طول متن بر حسب واحدهای UTF-16 (همان چیزی که entity لازم دارد)."""
    return len(str(text).encode("utf-16-le")) // 2


def full_bold_span(text):
    """(offset, length) برای Bold کردن کل متن."""
    return 0, u16_length(text)


def blocked_bold_span(text=None):
    """(offset, length) عبارت «سرگرمی فعال» داخل پیام غیرفعال بودن."""
    text = BLOCKED_NOTICE if text is None else text
    index = text.find(BLOCKED_BOLD_PART)
    if index < 0:
        return None
    return u16_length(text[:index]), u16_length(BLOCKED_BOLD_PART)


try:  # pragma: no cover - در محیط تست SPlusthon نصب نیست
    from splusthon.tl.types import MessageEntityBold
except ImportError:  # pragma: no cover
    class MessageEntityBold:
        def __init__(self, offset=0, length=0):
            self.offset = offset
            self.length = length


def bold_entities(spans):
    return [MessageEntityBold(offset=offset, length=length)
            for offset, length in spans if length]


async def _reply(event, text, spans):
    """پاسخ با Bold واقعی؛ اگر کلاینت entity نپذیرفت، متن ساده می‌رود."""
    entities = bold_entities(spans)
    try:
        return await event.reply(text, formatting_entities=entities)
    except TypeError:
        return await event.reply(text)


async def send_disabled_notice(event):
    """«🎮 بازی های روباه غیر فعال شد» — کل پیام Bold."""
    return await _reply(event, DISABLED_NOTICE, [full_bold_span(DISABLED_NOTICE)])


async def send_enabled_notice(event):
    """پیام فعال شدن — کل پیام Bold."""
    return await _reply(event, ENABLED_NOTICE, [full_bold_span(ENABLED_NOTICE)])


async def send_blocked_notice(event):
    """پیام «غیرفعال بودن» — فقط «سرگرمی فعال» Bold."""
    span = blocked_bold_span()
    return await _reply(event, BLOCKED_NOTICE, [span] if span else [])


# ------------------------- گاردِ مرکزیِ اجرای سرگرمی -------------------------
# هر دستوری که یک بازی/سرگرمی داخل خودِ ربات را «اجرا» می‌کند اینجا ثبت
# می‌شود. سایت بازی («سایت بازی»، «سایت»، «/game» …) عمداً اینجا نیست؛
# این قابلیت فقط سرگرمی‌های داخلی را کنترل می‌کند.
GAME_COMMANDS = frozenset({
    # بازی‌های قدیمی داخل message_handler
    "چیستان",
    "حدس ایموجی",
    "حدس پرچم",
    "اسم فامیل",
    "تصحیح کلمات",
    "چهار گزینه ای",
    "چهار گزینه‌ای",
    "جای خالی",
    "کی بیشتر بلده",
    "دروغ یا حقیقت",
    "جرعت", "جرات", "جرئت",
    "حقیقت", "حقیقت بگو",
    "جک",
    # بازی‌های Fox AI (همان مقادیر FOX_GAME_COMMANDS در روتر)
    "بخند یا بباز",
    "بقا",
    "جعبه شانسی",
    "خون آشام",
    "خون‌آشام",
    "معما",
    "حدس جمله",
    "ساخت جمله",
    "مین یاب",
    "بهترین جواب",
    "نبرد",
    "کارگاه",
    "شرکت",
})

# نیم‌فاصله/نویسه‌های عربی و فاصله‌های تکراری، تا «چهار گزینه‌ای» و
# «حدس ايموجي» هم درست تشخیص داده شوند.
_NORMALIZE_MAP = {
    "\u200c": " ",
    "\u200f": "",
    "\u200e": "",
    "\u064a": "\u06cc",
    "\u0643": "\u06a9",
}


def normalize(text):
    if not text:
        return ""
    value = str(text)
    for source, target in _NORMALIZE_MAP.items():
        value = value.replace(source, target)
    return " ".join(value.split())


def is_game_command(text):
    """آیا این متن یکی از دستورهای اجرای سرگرمی‌های داخلی است؟"""
    value = normalize(text)
    return value in GAME_COMMANDS or (text or "").strip() in GAME_COMMANDS


def blocks(chat_id, text):
    """گاردِ خالص (بدون I/O شبکه): آیا اجرای این دستور باید متوقف شود؟"""
    return is_game_command(text) and not is_enabled(chat_id)


async def guard(event, chat_id, text):
    """گاردِ مرکزی. اگر True برگرداند یعنی بازی نباید اجرا شود.

    وقتی سرگرمی گروه خاموش است: هیچ state ای ساخته نمی‌شود، هیچ جایزه/
    سکه‌ای پرداخت نمی‌شود و فقط پیام «غیرفعال بودن» ارسال می‌شود.
    """
    if not blocks(chat_id, text):
        return False
    await send_blocked_notice(event)
    return True
