"""فیلتر مستقل نام نمایشی/بیوگرافی؛ جدا از banned_words گروه."""
import json
import re
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "config" / "profile_access_blocks.json"
BLOCKED_TERMS = (
    "فرزند ایران", "جان فدای میهن", "فرزند ایران و جانفدای میهن",
    "آمریکا", "پرچم آمریکا", "پهلوی", "شاهزاده",
)


def _norm(value):
    value = str(value or "").lower()
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = re.sub(r"[#\u200c\u200d\u200f\u200e]", " ", value)
    return " ".join(value.split())


def _load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _bio(user):
    for name in ("about", "bio", "biography"):
        value = getattr(user, name, None)
        if value:
            return str(value)
    return ""


def reason(user):
    text = _norm(" ".join(filter(None, [getattr(user, "first_name", ""),
                                           getattr(user, "last_name", ""),
                                           getattr(user, "username", ""), _bio(user)])))
    for term in BLOCKED_TERMS:
        if _norm(term) in text:
            return term
    return None


def is_blocked(user_id):
    return str(user_id) in _load()


def block(user_id, reason_text):
    data = _load(); data[str(user_id)] = {"reason": reason_text}; _save(data)


def unblock(user_id):
    data = _load()
    if str(user_id) in data:
        data.pop(str(user_id)); _save(data)


def record_for(user_id):
    return _load().get(str(user_id))
