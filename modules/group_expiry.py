"""⏳ تاریخ انقضای گروه — قابلیتی کاملاً مستقل.

این ماژول هیچ وابستگی‌ای به بازی‌ها، حافظهٔ گروه، قفل‌ها، سکه‌ها یا هر
سیستم دیگری ندارد. تنها فایل ذخیره‌سازی آن ``config/group_expiry.json``
است و هیچ ماژول دیگری در آن نمی‌نویسد.

چهار دستور پشتیبانی‌شده و مدت دقیق آن‌ها:
    «۵ روز»   =  ۵ روز
    «یک هفته» =  ۷ روز
    «دو هفته» = ۱۴ روز
    «یک ماه»  = ۲۹ روز

نکات پیاده‌سازی:
  • تطبیق دستور «دقیق» است؛ هیچ ``startswith`` عمومی‌ای وجود ندارد، پس
    این سه عبارت هرگز با دستورهای دیگر اشتباه گرفته نمی‌شوند.
  • مهرهای زمانی به صورت UTC ذخیره می‌شوند تا تغییر منطقهٔ زمانی سیستم
    یا ری‌استارت، انقضا را جابه‌جا نکند. نمایش به وقت تهران است.
  • تبدیل تاریخ جلالی درون همین فایل انجام می‌شود تا وابستگی خارجی
    اضافه نشود.
"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.runtime_paths import runtime_config_file

# منبعِ مرکزیِ زمان و timezone پروژه (تهران).
from modules.time_utils import TEHRAN

FILE = runtime_config_file("group_expiry.json")

# --- دستورها ------------------------------------------------------------
FIVE_DAYS = "۵ روز"
ONE_WEEK = "یک هفته"
TWO_WEEKS = "دو هفته"
ONE_MONTH = "یک ماه"

DURATIONS = {
    FIVE_DAYS: 5,
    ONE_WEEK: 7,
    TWO_WEEKS: 14,
    ONE_MONTH: 29,
}
COMMANDS = frozenset(DURATIONS)

# دستور خبری «مهلت گروه» — تاریخ انقضا را تنظیم نمی‌کند، فقط مهلت
# باقی‌ماندهٔ واقعیِ همین گروه را از روی همان رکورد انقضای موجود می‌خواند.
REMAINING_COMMAND = "مهلت گروه"

# --- پیام‌ها ------------------------------------------------------------
EXPIRED_MESSAGE = (
    "⛔ مدت زمان فعال بودن گروه به پایان رسید و گروه به‌صورت خودکار غیرفعال شد"
)
SET_HEADER = "✅ تاریخ انقضای گروه تنظیم شد."
ACTIVATED_LABEL = "📅 تاریخ فعال‌سازی:"
EXPIRES_LABEL = "⏳ تاریخ انقضا:"

_cache = None
_cache_mtime = None


# ---------------------------------------------------------------------------
# یکسان‌سازی متن دستور
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
    """متن را برای مقایسهٔ دقیق یکسان می‌کند (نیم‌فاصله، عربی، فاصله‌ها)."""
    value = str(text or "")
    for source, target in _NORMALIZE.items():
        value = value.replace(source, target)
    return " ".join(value.split())


def match_command(text):
    """اگر متن *دقیقاً* یکی از سه دستور باشد همان را برمی‌گرداند، وگرنه None.

    تطبیق کامل است: «یک هفته دیگر» یا «ثبت یک ماه» تطبیق نمی‌کنند، پس این
    مسیر هرگز با دستورهای دیگر تداخل نمی‌کند.
    """
    normalized = normalize_command(text)
    return normalized if normalized in DURATIONS else None


def match_remaining_command(text):
    """اگر متن *دقیقاً* دستور «مهلت گروه» باشد آن را برمی‌گرداند.

    مثل دستورهای ثبت مهلت، تطبیق کامل است: «مهلت گروه من» یا «گروه مهلت»
    تطبیق نمی‌کنند تا هیچ تداخلی با مسیرهای دیگر پیش نیاید.
    """
    normalized = normalize_command(text)
    return REMAINING_COMMAND if normalized == REMAINING_COMMAND else None


def duration_days(command):
    return DURATIONS.get(normalize_command(command))


# ---------------------------------------------------------------------------
# شناسهٔ گروه
# ---------------------------------------------------------------------------
_CHANNEL_ID_OFFSET = 1_000_000_000_000


def _group_key(group_id):
    """کلید پایدار: -100123 و 123 به یک کلید نگاشت می‌شوند."""
    try:
        value = int(group_id)
    except (TypeError, ValueError):
        return str(group_id)
    if value <= -_CHANNEL_ID_OFFSET:
        value = abs(value) - _CHANNEL_ID_OFFSET
    elif value < 0:
        value = abs(value)
    return str(value)


# ---------------------------------------------------------------------------
# ذخیره‌سازی ماندگار
# ---------------------------------------------------------------------------
def _mtime():
    try:
        return FILE.stat().st_mtime_ns
    except OSError:
        return None


def _load():
    global _cache, _cache_mtime
    mtime = _mtime()
    if _cache is not None and mtime == _cache_mtime:
        return _cache
    if mtime is None:
        _cache = {}
    else:
        try:
            raw = json.loads(FILE.read_text(encoding="utf-8"))
            _cache = raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            # فایل خراب نباید ربات را از کار بیندازد.
            _cache = {}
    _cache_mtime = mtime
    return _cache


def _save(data):
    """نوشتن اتمی: فایل نیمه‌نوشته پس از قطع برق باقی نمی‌ماند."""
    global _cache, _cache_mtime
    FILE.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(dir=str(FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, FILE)
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    _cache = data
    _cache_mtime = _mtime()


def reset_all():
    """پاک‌سازی کامل — فقط برای تست."""
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None
    try:
        FILE.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# تاریخ جلالی و قالب‌بندی
# ---------------------------------------------------------------------------
_JALALI_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)


def _to_jalali(year, month, day):
    g_days = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = year + 1 if month > 2 else year
    days = (
        355666 + 365 * year + (gy2 + 3) // 4 - (gy2 + 99) // 100
        + (gy2 + 399) // 400 + day + g_days[month - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def format_datetime(moment):
    """«۱۴۰۴/۰۵/۰۹ - ساعت ۱۴:۳۰» به وقت تهران."""
    local = moment.astimezone(TEHRAN)
    jy, jm, jd = _to_jalali(local.year, local.month, local.day)
    text = (
        f"{jy:04d}/{jm:02d}/{jd:02d} "
        f"({jd} {_JALALI_MONTHS[jm - 1]} {jy}) "
        f"- ساعت {local.hour:02d}:{local.minute:02d}"
    )
    return text.translate(str.maketrans("0123456789", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"))


# ---------------------------------------------------------------------------
# عملیات اصلی
# ---------------------------------------------------------------------------
def _now():
    return datetime.now(timezone.utc)


def set_expiry(group_id, command, title=None, now=None):
    """تاریخ انقضا را از همین لحظه تنظیم (یا جایگزین) می‌کند.

    ``None`` یعنی دستور معتبر نبود. خروجی موفق یک dict شامل
    ``activated_at`` و ``expires_at`` (هر دو datetime آگاه از منطقهٔ زمانی).
    """
    days = duration_days(command)
    if days is None:
        return None

    started = now or _now()
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    ends = started + timedelta(days=days)

    data = _load()
    record = {
        "command": normalize_command(command),
        "days": days,
        "activated_at": started.astimezone(timezone.utc).isoformat(),
        "expires_at": ends.astimezone(timezone.utc).isoformat(),
        # پس از تمدید دوباره، پرچم اعلام پاک می‌شود تا اگر باز منقضی شد
        # دوباره پیام داده شود.
        "notified": False,
    }
    if title:
        record["title"] = title
    data = dict(data)
    data[_group_key(group_id)] = record
    _save(data)
    return {
        "command": record["command"],
        "days": days,
        "activated_at": started,
        "expires_at": ends,
    }


def get_record(group_id):
    record = _load().get(_group_key(group_id))
    return dict(record) if record else None


def _parse(value):
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def expires_at(group_id):
    record = get_record(group_id)
    return _parse(record.get("expires_at")) if record else None


def activated_at(group_id):
    record = get_record(group_id)
    return _parse(record.get("activated_at")) if record else None


def has_expiry(group_id):
    return expires_at(group_id) is not None


def is_expired(group_id, now=None):
    """آیا مهلت این گروه تمام شده است.

    گروهی که هرگز تاریخ انقضا نگرفته «منقضی» نیست؛ این قابلیت فقط روی
    گروه‌هایی اثر دارد که مالک برایشان مهلت تعیین کرده است.
    """
    ends = expires_at(group_id)
    if ends is None:
        return False
    return (now or _now()) >= ends


def seconds_left(group_id, now=None):
    ends = expires_at(group_id)
    if ends is None:
        return None
    return max(0.0, (ends - (now or _now())).total_seconds())


def clear_expiry(group_id):
    """رکورد انقضای یک گروه را حذف می‌کند."""
    data = _load()
    key = _group_key(group_id)
    if key not in data:
        return False
    data = dict(data)
    del data[key]
    _save(data)
    return True


def update_title(group_id, title):
    """نام گروه را فقط روی رکورد انقضای «ازقبل موجود» به‌روز می‌کند.

    برای گروهی که رکورد انقضا ندارد هیچ رکوردی ساخته نمی‌شود و هیچ فیلد
    دیگری (تاریخ‌ها، پرچم اعلام، مدت) دست نمی‌خورد. خروجی: True فقط اگر
    عنوان واقعاً تغییر کرد.
    """
    title = str(title or "").strip()
    if not title:
        return False
    data = _load()
    key = _group_key(group_id)
    record = data.get(key)
    if not isinstance(record, dict):
        return False
    if str(record.get("title") or "").strip() == title:
        return False
    data = dict(data)
    updated = dict(record)
    updated["title"] = title
    data[key] = updated
    _save(data)
    return True


def was_notified(group_id):
    record = get_record(group_id)
    return bool(record and record.get("notified"))


def mark_notified(group_id):
    """اعلام غیرفعال‌سازی را ثبت می‌کند تا پیام تکراری ارسال نشود."""
    data = _load()
    key = _group_key(group_id)
    record = data.get(key)
    if not record or record.get("notified"):
        return False
    data = dict(data)
    updated = dict(record)
    updated["notified"] = True
    data[key] = updated
    _save(data)
    return True


def due_groups(now=None):
    """گروه‌هایی که همین حالا منقضی شده‌اند و هنوز اعلام نشده‌اند.

    خروجی فهرستی از ``(group_key, record)`` است. حلقهٔ پس‌زمینه از این
    استفاده می‌کند تا بدون نیاز به هیچ پیامی گروه را ببندد.
    """
    moment = now or _now()
    result = []
    for key, record in _load().items():
        if record.get("notified"):
            continue
        ends = _parse(record.get("expires_at"))
        if ends is not None and moment >= ends:
            result.append((key, dict(record)))
    return result


def all_records():
    return {key: dict(value) for key, value in _load().items()}


# ---------------------------------------------------------------------------
# ساخت پیام تأیید همراه با entity ها
# ---------------------------------------------------------------------------
def _u16(value):
    return len(value.encode("utf-16-le")) // 2


def build_confirmation(activated, expires):
    """متن تأیید و entity ها.

    هر دو تاریخ داخل نقل‌قول شیشه‌ای (Blockquote) و به صورت Bold هستند.
    خروجی ``(text, [(kind, offset, length), ...])`` است تا این ماژول به
    splusthon وابسته نشود؛ فراخوان، entity واقعی را می‌سازد.
    """
    activated_text = format_datetime(activated)
    expires_text = format_datetime(expires)
    text = (
        f"{SET_HEADER}\n\n"
        f"{ACTIVATED_LABEL}\n{activated_text}\n\n"
        f"{EXPIRES_LABEL}\n{expires_text}"
    )
    spans = []
    for value in (activated_text, expires_text):
        start = text.index(value)
        offset = _u16(text[:start])
        length = _u16(value)
        spans.append(("blockquote", offset, length))
        spans.append(("bold", offset, length))
    return text, spans


def build_expired_message():
    """متن غیرفعال‌سازی خودکار، کاملاً Bold."""
    text = EXPIRED_MESSAGE
    return text, [("bold", 0, _u16(text))]


# ---------------------------------------------------------------------------
# پیام «مهلت گروه» — نمایش مهلت باقی‌ماندهٔ واقعی
# ---------------------------------------------------------------------------
_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

REMAINING_NO_RECORD = "ثبت نشده"
REMAINING_EXPIRED = "منقضی شده"
RENEW_LINE = "برای تمدید اشتراک : 𝄞 @aifox_bot"


def format_remaining(seconds):
    """مدت باقی‌مانده را به فارسی خوانا تبدیل می‌کند.

    ``None`` یعنی گروه اصلاً تاریخ انقضا ندارد؛ عدد <= ۰ یعنی مهلت تمام
    شده است. قالب با گزارش «لیست انقضا» یکسان است: روز/ساعت با «و»، و
    دقیقه فقط وقتی روز و ساعت صفر باشند.
    """
    if seconds is None:
        return REMAINING_NO_RECORD
    total = int(seconds)
    if total <= 0:
        return REMAINING_EXPIRED
    days, remainder = divmod(total, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days} روز")
    if hours or days:
        parts.append(f"{hours} ساعت")
    if not days and not hours:
        parts.append(f"{minutes} دقیقه" if minutes else "کمتر از ۱ دقیقه")
    return " و ".join(parts).translate(_PERSIAN_DIGITS)


def build_remaining_message(title, remaining_text):
    """متن و entity های دستور «مهلت گروه».

    خروجی دقیقاً سه خط است و فقط دو برچسب «گروه» و «مهلت باقی مانده»
    Bold هستند؛ نام گروه، مدت و خط تمدید عادی می‌مانند و هیچ نقل‌قول
    شیشه‌ای استفاده نمی‌شود. خروجی ``(text, [(kind, offset, length)])``.
    """
    title = str(title or "").strip() or "گروه بدون نام"
    line1 = f"↻- گروه : {title}"
    line2 = f"مهلت باقی مانده : {remaining_text}"
    text = f"{line1}\n{line2}\n{RENEW_LINE}"

    spans = []
    # برچسب «گروه» در خط اول همیشه قبل از نام گروه می‌آید، پس اولین
    # جایگاه، همان برچسب است. خط دوم هم با برچسب «مهلت باقی مانده» شروع
    # می‌شود. محاسبه بر اساس خطوط، حتی اگر نام گروه این کلمه‌ها را داشته
    # باشد، جای درستی را می‌دهد.
    label1 = "گروه"
    label1_start = line1.index(label1)
    spans.append(("bold", _u16(line1[:label1_start]), _u16(label1)))
    label2 = "مهلت باقی مانده"
    offset2 = _u16(line1) + 1  # +1 برای «\n» بین دو خط
    spans.append(("bold", offset2, _u16(label2)))
    return text, spans
