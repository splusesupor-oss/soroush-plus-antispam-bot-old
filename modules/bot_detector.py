"""تشخیصِ مستقیمِ رباتِ دیگر در گروه و غیرفعال‌سازیِ روباه.

قانونِ اصلی:
  - «ربات بودن» فقط و فقط از فیلدِ مستقیمِ API (``User.bot``) تعیین می‌شود؛
    هیچ حدسی بر اساسِ سرعتِ پیام، نامِ کاربری یا بیوگرافی زده نمی‌شود. بنابراین
    کاربرِ عادی (که فیلدِ bot ندارد/False است) هرگز به‌اشتباه ربات تشخیص داده
    نمی‌شود.
  - حسابِ خودِ روباه (``bot.bot_account_id`` یا نام‌های‌شناسه) هرگز هدفِ این
    ماژول قرار نمی‌گیرد.

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
    """آیا فرستنده یک حسابِ رباتِ واقعی است (تشخیصِ مستقیمِ API)؟

    فقط بر اساسِ فیلدِ ``User.bot``؛ اگر فیلد نباشد یا False باشد، ربات نیست.
    """
    if user is None:
        return False
    return bool(getattr(user, "bot", None))


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
