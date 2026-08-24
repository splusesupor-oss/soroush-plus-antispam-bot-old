"""فیلتر مستقل نام نمایشی/بیوگرافی؛ جدا از banned_words گروه."""
import json
import os
import re
import tempfile

from modules.runtime_paths import runtime_config_file

FILE = runtime_config_file("profile_access_blocks.json")
_CACHE = None

PERSIAN_CHARS = r"a-zA-Z0-9\u0621-\u0628\u062a-\u063a\u0641-\u0642\u0644-\u0648\u064e-\u065f\u067e\u0686\u0698\u06a9\u06af\u06cc\u0629\u0649\u064a\u0622\u0623\u0625\u0671"

BLOCKED_TERMS = (
    "پهلوی",
    "شاهزاده",
    "شاه زاده",
    "دلباخته پهلوی",
    "رضا شاه",
    "رضاشاه",
    "محمدرضا شاه",
    "محمدرضاشاه",
    "جان فدای میهن",
    "جانفدای میهن",
    "فرزند ایران",
    "پرچم آمریکا",
    "آمریکا",
    "شاه",
)


def _norm(value):
    if not value:
        return ""
    t = re.sub(r"[\u0640\u064b-\u065f]", "", str(value))
    t = re.sub(r"[\u200c\u200d\u200e\u200f\ufeff\u00a0\-_.,/\\;:!؟،؛|()\[\]{}<>+=*&^%$#@~\"\'`«»…]+", " ", t)
    t = t.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").replace("آ", "ا").replace("أ", "ا").replace("إ", "ا")
    return " ".join(t.lower().split())


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
            json.dump(data, stream, ensure_ascii=False, indent=2)
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
    if user is None:
        return None
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    username = getattr(user, "username", "") or ""
    user_bio = bio if bio is not None else _bio(user)

    text = _norm(f"{first} {last} {username} {user_bio}".strip())
    if not text:
        return None

    for term in BLOCKED_TERMS:
        norm_term = _norm(term)
        if not norm_term:
            continue
        pattern = re.compile(rf"(?<![{PERSIAN_CHARS}]){re.escape(norm_term)}(?![{PERSIAN_CHARS}])")
        if pattern.search(text):
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
