"""تشخیص مستقل نام‌های تبلیغاتی؛ جدا از فیلتر متن گروه."""
import re

_TERMS = (
    r"بیو\s*چک", r"چک\s*بیو", r"بیوگرافی\s*چک", r"بیومو\s*(?:چک|ببینید|ببین)",
    r"بیو.*(?:فیلم|لینک|چک|ببین)", r"(?:نود|پیوی)\s*رایگان",
    r"پیوی\s*رایگان", r"خاله\s*نازنین",
)
_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _TERMS)


def _norm(value):
    value = str(value or "").lower().replace("ي", "ی").replace("ك", "ک").replace("_", " ")
    value = re.sub(r"[\u200c\u200d\u200f\u200e]", " ", value)
    return " ".join(value.split())


def display_name(user):
    name = " ".join(x for x in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if x).strip()
    if name:
        return name
    username = getattr(user, "username", None)
    return f"@{str(username).lstrip('@')}" if username else "کاربر ناشناس"


def reason(user):
    username = _norm(getattr(user, "username", None))
    name = _norm(" ".join(x for x in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if x))
    for value in (username, name):
        for pattern in _PATTERNS:
            if pattern.search(value):
                return pattern.pattern
    return None
