"""فیلتر مستقل نام نمایشی/بیوگرافی؛ جدا از banned_words گروه."""
import json
import os
import re
import tempfile

from modules.runtime_paths import runtime_config_file

FILE = runtime_config_file("profile_access_blocks.json")
_CACHE = None

PERSIAN_WORD_CHARS = r"a-zA-Z0-9_\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFC"

BLOCKED_TERMS = (
    "پهلوی",
    "pahlavi",
    "شاهزاده",
    "شاه زاده",
    "shahzadeh",
    "shahzade",
    "دلباخته پهلوی",
    "رضا شاه",
    "رضاشاه",
    "rezashah",
    "reza shah",
    "محمدرضا شاه",
    "محمدرضاشاه",
    "جان فدای میهن",
    "جانفدای میهن",
    "فرزند ایران",
    "farzand iran",
    "farzande iran",
    "پرچم آمریکا",
    "آمریکا",
    "usa",
    "شاه",
    "shah",
)


def _norm(value):
    if not value:
        return ""
    t = str(value).lower()
    t = t.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").replace("آ", "ا").replace("أ", "ا").replace("إ", "ا")
    t = re.sub(r"[\u0640\u064b-\u065f]", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


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


def _extract_user_strings(user, bio=None):
    if user is None:
        return []
    parts = []
    if isinstance(user, dict):
        for k in ("first_name", "last_name", "username", "name", "title", "about", "bio", "biography"):
            v = user.get(k)
            if v:
                parts.append(str(v))
    else:
        for k in ("first_name", "last_name", "username", "name", "title", "about", "bio", "biography"):
            v = getattr(user, k, None)
            if v:
                parts.append(str(v))
    if bio:
        parts.append(str(bio))
    return parts


def reason(user, bio=None):
    strings = _extract_user_strings(user, bio)
    if not strings:
        return None

    raw_combined = " ".join(strings).strip()
    norm_text = _norm(raw_combined)
    compact_text = norm_text.replace(" ", "")

    for term in BLOCKED_TERMS:
        norm_term = _norm(term)
        compact_term = norm_term.replace(" ", "")
        if not norm_term:
            continue
        if term in ("شاه", "shah"):
            pattern = re.compile(rf"(?<![{PERSIAN_WORD_CHARS}]){re.escape(norm_term)}(?![{PERSIAN_WORD_CHARS}])")
            if pattern.search(norm_text):
                return term
        else:
            if norm_term in norm_text or compact_term in compact_text:
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

