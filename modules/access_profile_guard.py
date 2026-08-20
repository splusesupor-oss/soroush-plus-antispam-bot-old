"""فیلتر مستقل نام نمایشی/بیوگرافی؛ جدا از banned_words گروه."""
import json
import os
import re
import tempfile

from modules.runtime_paths import runtime_config_file

FILE = runtime_config_file("profile_access_blocks.json")
_CACHE = None
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
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
        _CACHE = data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        _CACHE = {}
    return _CACHE


def _save(data):
    """Atomic write; callers already avoid no-op rewrites."""
    global _CACHE
    _CACHE = data
    FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, FILE)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _bio(user):
    for name in ("about", "bio", "biography"):
        value = getattr(user, name, None)
        if value:
            return str(value)
    return ""


def reason(user, bio=None):
    text = _norm(" ".join(filter(None, [getattr(user, "first_name", ""),
                                           getattr(user, "last_name", ""),
                                           getattr(user, "username", ""),
                                           bio if bio is not None else _bio(user)])))
    for term in BLOCKED_TERMS:
        if _norm(term) in text:
            return term
    return None


def is_blocked(user_id):
    return str(user_id) in _load()


def block(user_id, reason_text):
    """Persist a block only when it is new or its reason changed."""
    data = _load()
    key = str(user_id)
    record = {"reason": reason_text}
    if data.get(key) == record:
        return False
    data[key] = record
    _save(data)
    return True


def unblock(user_id):
    data = _load()
    if str(user_id) in data:
        data.pop(str(user_id))
        _save(data)
        return True
    return False


def record_for(user_id):
    return _load().get(str(user_id))
