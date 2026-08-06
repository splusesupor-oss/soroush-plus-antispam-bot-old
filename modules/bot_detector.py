"""تشخیصِ مستقیمِ رباتِ دیگر در گروه و غیرفعال‌سازیِ روباه.

قانونِ اصلی:
  - «ربات بودن» از فیلدِ مستقیمِ API (``User.bot``) تعیین می‌شود؛ هیچ حدسی بر
    اساسِ سرعتِ پیام، نامِ کاربری یا بیوگرافی زده نمی‌شود. بنابراین کاربرِ عادی
    هرگز به‌اشتباه ربات تشخیص داده نمی‌شود.
  - در پیامِ گروه، آبجکتِ sender اغلب یک entityِ خلاصه است که ``bot`` آن
    ``None`` است (پرنشده). در آن صورت برای تصمیمِ قطعی، entityِ کاملِ کاربر با
    ``client.get_entity`` (یعنی GetUsers) گرفته می‌شود که ``User`` کامل را با
    ``bot`` قطعی برمی‌گرداند. فقط اگر ``bot is True`` باشد ربات اعلام می‌شود.
  - حسابِ خودِ روباه هرگز هدفِ این ماژول قرار نمی‌گیرد.

وضعیتِ هر گروهِ غیرفعال‌شده در ``config/bot_disabled_groups.json`` ذخیره
می‌شود تا بعد از هر پیام روباه دوباره فعال نشود و پیامِ اطلاع‌رسانی فقط یک
بار ارسال شود.
"""
import json
from datetime import datetime
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent / "config"
_FILE = _BASE / "bot_disabled_groups.json"

# دستورِ مجاز برای فعال‌سازیِ دوباره (مالک/ادمین).
REENABLE_COMMAND = "فعال کردن روباه"

# کشِ درون‌حافظه‌ایِ وضعیتِ قطعیِ نوعِ حسابِ هر user_id (برای پرهیز از
# fetchِ تکراری روی هر پیام).
_KNOWN_BOT_IDS = set()    # قطعاً ربات
_KNOWN_HUMAN_IDS = set()  # قطعاً کاربرِ عادی


def _load():
    try:
        if _FILE.exists():
            data = json.loads(_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def _save(data):
    try:
        _BASE.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def is_bot_sender(user):
    """آیا فرستنده یک حسابِ رباتِ واقعی است (فقط با فیلدِ مستقیمِ API)؟

    بر اساسِ ``User.bot``:
      - ``bot is True`` → ربات.
      - ``bot is False`` → کاربرِ عادی (قطعی).
      - ``bot is None`` (entityِ ناقص) → نامشخص؛ با ``resolve_is_bot`` باید
        entityِ کامل گرفته شود. این تابعِ ساده فقط برای مقدارِ قطعیِ True است.
    """
    if user is None:
        return False
    return getattr(user, "bot", None) is True


async def resolve_is_bot(client, user, user_id):
    """تشخیصِ قطعیِ ربات بودنِ فرستنده، حتی اگر entityِ خلاصه باشد.

    ترتیب:
      1. اگر قبلاً برای این user_id قطعی‌سازی شده، از کش استفاده کن.
      2. اگر ``user.bot is True`` → ربات؛ ``False`` → انسان.
      3. اگر ``user.bot is None`` → با ``client.get_entity`` entityِ کاملِ
         کاربر را بگیر و فیلدِ bot را بخوان (GetUsers → User کامل).
         فقط ``bot is True`` → ربات.

    خروجی: bool.
    """
    if user_id in _KNOWN_BOT_IDS:
        return True
    if user_id in _KNOWN_HUMAN_IDS:
        return False
    if user is not None and getattr(user, "bot", None) is not None:
        _remember(user_id, user.bot)
        return bool(user.bot)
    # entityِ ناقص → fetch کامل
    try:
        full = await client.get_entity(user if user is not None else user_id)
    except Exception:
        return False
    is_bot = getattr(full, "bot", None) is True
    _remember(user_id, is_bot)
    return is_bot


def _remember(user_id, is_bot):
    if user_id is None:
        return
    if is_bot:
        _KNOWN_BOT_IDS.add(user_id)
    else:
        _KNOWN_HUMAN_IDS.add(user_id)


def display(user):
    """نامِ نمایشیِ ربات: @username در اولویت، بعد نامِ نمایشی."""
    if user is None:
        return "ربات"
    username = getattr(user, "username", None)
    if username:
        return "@" + str(username).lstrip("@")
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    name = " ".join(part for part in (first, last) if part).strip()
    return name or "ربات"


def disable_for_bot(chat_id, bot_user):
    """گروه را برای رباتِ شناسایی‌شده غیرفعال ثبت می‌کند (ماندگار)."""
    data = _load()
    data[str(chat_id)] = {
        "bot_id": getattr(bot_user, "id", None),
        "bot_name": display(bot_user),
        "disabled_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save(data)


def is_disabled(chat_id):
    """آیا این گروه به دلیلِ رباتِ دیگر غیرفعال شده است؟"""
    return str(chat_id) in _load()


def reenable(chat_id):
    """فعال‌سازیِ دوبارهٔ روباه در این گروه (حذفِ وضعیتِ غیرفعال)."""
    data = _load()
    if str(chat_id) in data:
        del data[str(chat_id)]
        _save(data)
        return True
    return False


def disabled_bot_name(chat_id):
    return _load().get(str(chat_id), {}).get("bot_name", "ربات")


def sender_dump(user):
    """نمایشِ کاملِ دادهٔ sender برای لاگِ تشخیصی (هرآنچه API داده است)."""
    if user is None:
        return repr(None)
    try:
        to_dict = getattr(user, "to_dict", None)
        if callable(to_dict):
            return json.dumps(to_dict(), ensure_ascii=False, default=str)
    except Exception:
        pass
    try:
        return json.dumps(vars(user), ensure_ascii=False, default=str)
    except Exception:
        return repr(user)

