"""تشخیص مستقل نام‌های تبلیغاتی؛ جدا از فیلتر متن گروه."""
import re

from modules.user_display import format_user

_TERMS = (
    r"بیو\s*چک", r"چک\s*بیو", r"بیوگرافی\s*چک", r"بیومو\s*(?:چک|ببینید|ببین)",
    r"بیو.*(?:فیلم|لینک|چک|ببین)", r"(?:نود|پیوی)\s*رایگان",
    r"پیوی\s*رایگان", r"خاله\s*نازنین",
    # «رایگان» به‌تنهایی هم نام تبلیغاتی است و مستقیم بن می‌شود.
    r"رایگان",
)
_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _TERMS)


def _norm(value):
    value = str(value or "").lower().replace("ي", "ی").replace("ك", "ک").replace("_", " ")
    # حذف «کشیده» (ـ tatweel): «بیـو چک» و «رایـــگان» → «بیو چک» و «رایگان»
    value = value.replace("\u0640", "")
    value = re.sub(r"[\u200c\u200d\u200f\u200e]", " ", value)
    return " ".join(value.split())


def _collapse(value):
    """جمع کردن حروف تکراری: «بیوچکک» و «بییییو چک» → «بیوچک» و «بیو چک».

    فقط به‌عنوان نسخهٔ دوم برای تطبیق استفاده می‌شود؛ متن اصلی هم جدا
    بررسی می‌شود تا هیچ تشخیصِ قبلی از دست نرود.
    """
    return re.sub(r"(.)\1+", r"\1", value)


def display_name(user):
    return format_user(user)


def reason(user):
    username = _norm(getattr(user, "username", None))
    name = _norm(" ".join(x for x in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if x))
    for value in (username, name):
        if not value:
            continue
        # هم متن عادی و هم نسخهٔ بدون حروف تکراری بررسی می‌شود تا
        # نوشتار کشیده (بیوچکک، بیــو چک، بییییو چک) هم گرفته شود.
        for candidate in (value, _collapse(value)):
            for pattern in _PATTERNS:
                if pattern.search(candidate):
                    return pattern.pattern
    return None
