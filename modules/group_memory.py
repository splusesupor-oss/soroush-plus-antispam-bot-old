"""Persistent per-group display-name memory for users."""
import json
import re
from pathlib import Path
from random import SystemRandom

from modules.group_id import normalize_group_id

FILE = Path(__file__).resolve().parent.parent / "config" / "group_memory.json"
MAX_NAME_LENGTH = 20

# Common names make sentence inputs predictable: "ثبت علی پسر محمد" stores "علی".
KNOWN_NAMES = frozenset({
    "علی", "محمد", "رضا", "حسین", "مهدی", "امیر", "امیرحسین", "امیرعلی",
    "سجاد", "مجتبی", "مصطفی", "یوسف", "سعید", "حمید", "داوود", "نوید", "میلاد",
    "نیما", "سینا", "کیان", "کیارش", "سام", "سامان", "آرمان", "آرین", "آراد",
    "پارسا", "پویان", "فرهاد", "فرید", "فرزاد", "کوروش", "بهرام", "بهنام", "رامین",
    "عماد", "emad", "ali", "mohammad", "reza", "hossein", "amir", "sina", "armin",
    "maryam", "sara", "melika", "niloofar", "fatemeh", "zahra",
    "مریم", "ملیکا", "سارا", "زهرا", "فاطمه", "نرگس", "نگار", "نیلوفر", "مهسا",
    "هلیا", "هانیه", "یاسمن", "یسنا", "ترانه", "ریحانه", "رها", "روژان", "آوا",
    "آرزو", "آیدا", "بهاره", "پریا", "نازنین", "شادی", "سمیه", "لیلا", "مهناز",
})
SENTENCE_WORDS = frozenset({
    "من", "هستم", "استم", "اسم", "نام", "پسر", "دختر", "خوب", "هست", "این", "یک",
    "لقب", "برای", "ذخیره", "شدن", "است", "the", "is", "i", "am", "my", "name",
})
NICKNAMES = frozenset({"روباه", "فاکس", "شادو", "شاهین", "نوا", "آذر", "لئو", "مکس"})
BANNED_TERMS = frozenset({
    "فحش", "کیر", "کس", "جنده", "حرومزاده", "احمق", "کثافت", "لعنتی", "گوه",
})
_NAME_RE = re.compile(r"^[A-Za-zآ-یءئؤة]+(?:[ _-][A-Za-zآ-یءئؤة]+)?$")


def _normal(value):
    return " ".join(str(value or "").strip().lower().replace("ي", "ی").replace("ك", "ک").split())


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _group_key(chat_id):
    return normalize_group_id(chat_id)


def get_name(chat_id, user_id):
    return _load().get(_group_key(chat_id), {}).get(str(user_id), {}).get("name")


def set_name(chat_id, user_id, name):
    data = _load()
    group = data.setdefault(_group_key(chat_id), {})
    group[str(user_id)] = {"name": name}
    _save(data)
    return name


def remove_name(chat_id, user_id):
    data = _load()
    group = data.get(_group_key(chat_id), {})
    if str(user_id) not in group:
        return False
    del group[str(user_id)]
    if not group:
        data.pop(_group_key(chat_id), None)
    _save(data)
    return True


def extract_name(text):
    """Return (name, error). Persian known names win over sentence filler words."""
    value = " ".join(str(text or "").strip().split())
    if not value:
        return None, "empty"
    if len(value) > 80:
        return None, "too_long"
    if any(term in _normal(value) for term in BANNED_TERMS):
        return None, "invalid"
    words = [word.strip(".,!؟?!") for word in value.split()]
    words = [word for word in words if word and _normal(word) not in SENTENCE_WORDS]
    if not words:
        return None, "invalid"
    first = words[0]
    candidate = first
    if len(words) >= 2:
        second = words[1]
        # A short Latin two-word nickname such as "Emad Fox" is allowed,
        # including when its first word is also a common real name.
        if re.fullmatch(r"[A-Za-z]{2,12}", first) and re.fullmatch(r"[A-Za-z]{2,12}", second):
            candidate = f"{first} {second}"
    normalized = _normal(candidate)
    if len(candidate) > MAX_NAME_LENGTH:
        return None, "too_long"
    if not _NAME_RE.fullmatch(candidate) or len(normalized) < 2:
        return None, "invalid"
    if (
        _normal(first) not in KNOWN_NAMES
        and _normal(first) not in NICKNAMES
        and not re.fullmatch(r"[A-Za-z]{2,12}(?: [A-Za-z]{2,12})?", candidate)
    ):
        return None, "invalid"
    if any(term in normalized for term in BANNED_TERMS):
        return None, "invalid"
    return candidate, None


def friendly_reply(name, text):
    key = _normal(text)
    replies = {
        "سلام": (
            "سلام {name} 🦊", "سلام {name} 👋", "سلام {name}، خوش اومدی ✨",
        ),
        "خوبی": (
            "خوبم {name} 😄 تو خوبی؟", "اوکی‌ام {name} 🦊", "خوبم {name}، تو چطوری؟",
        ),
        "چه خبر": (
            "چه خبر {name}؟ 😎", "فعلاً همه‌چی خوبه {name} ✨", "خبر خاصی نیست {name} 🦊",
        ),
        "ربات": (
            "جانم {name} 🦊", "هستم {name} 👋", "بله {name}، بگو 😄",
        ),
    }
    options = replies.get(key)
    return SystemRandom().choice(options).format(name=name) if options else None
