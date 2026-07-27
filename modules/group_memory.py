"""Persistent per-group display-name memory for users."""
import json
import re
from pathlib import Path
from random import SystemRandom

from modules import persian_names
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
# پیشوندهای احترامی که همراه نام می‌آیند.
HONORIFIC_PREFIXES = frozenset({"سید", "سیده", "میر", "شیخ", "حاج", "حاجی"})
BANNED_TERMS = frozenset({
    "فحش", "کیر", "کس", "جنده", "حرومزاده", "احمق", "کثافت", "لعنتی", "گوه",
})
_NAME_RE = re.compile(r"^[A-Za-zآ-یءئؤة]+(?:[ _-][A-Za-zآ-یءئؤة]+)?$")


def _normal(value):
    return " ".join(str(value or "").strip().lower().replace("ي", "ی").replace("ك", "ک").split())


def _has_banned_term(value):
    """آیا متن حاوی واژهٔ رکیک است.

    مقایسه واژه‌به‌واژه است، نه زیررشته‌ای: جستجوی زیررشته‌ای نام‌های واقعی
    مثل «کسری»، «کسرا» یا «مکسیم» را قربانی می‌کرد چون «کس» درونشان هست.
    نامی که خودش در دیتابیس ثبت شده هرگز رکیک شمرده نمی‌شود.
    """
    normalized = _normal(value)
    if not normalized:
        return False
    if persian_names.is_known_name(normalized):
        return False
    tokens = [token.strip("‌_-.,!؟?") for token in normalized.split()]
    for token in tokens:
        if not token:
            continue
        if token in BANNED_TERMS:
            return True
        # واژه‌ای که نام معتبر نیست ولی واژهٔ رکیک را در خود دارد.
        if not persian_names.is_known_name(token):
            if any(term in token for term in BANNED_TERMS):
                return True
    return False


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
    """Return (name, error).

    اعتبارسنجی روی دیتابیس جامع نام‌های فارسی انجام می‌شود
    (``modules/persian_names.py`` با ~۲۴٬۵۰۰ نام دخترانه و پسرانه)، نه روی یک
    لیست کوچک دست‌نویس. هر نام واقعی که در آن دیتابیس باشد پذیرفته می‌شود؛
    فقط ورودی نامعتبر، توهین‌آمیز یا نامی که در هیچ منبعی نیست رد می‌شود.
    """
    value = " ".join(str(text or "").strip().split())
    if not value:
        return None, "empty"
    if len(value) > 80:
        return None, "too_long"
    if _has_banned_term(value):
        return None, "invalid"
    words = [word.strip(".,!؟?!") for word in value.split()]
    words = [word for word in words if word and _normal(word) not in SENTENCE_WORDS]
    if not words:
        return None, "invalid"

    # پیشوند احترامی مثل «سید» بخشی از نام است، نه خودِ نام.
    if len(words) >= 2 and _normal(words[0]) in HONORIFIC_PREFIXES:
        joined = f"{words[0]} {words[1]}"
        if persian_names.is_known_name(joined) or persian_names.is_known_name(
            words[0] + words[1]
        ) or persian_names.is_known_name(words[1]):
            words = [joined] + words[2:]

    first = words[0]
    candidate = first
    if len(words) >= 2:
        second = words[1]
        # نام مرکب فارسی مثل «محمد رضا» یا «امیر حسین» یک نام کامل است.
        if persian_names.is_known_name(f"{first} {second}"):
            candidate = f"{first} {second}"
        # لقب دوکلمه‌ای لاتین مثل "Emad Fox" هم مجاز است.
        elif re.fullmatch(r"[A-Za-z]{2,12}", first) and re.fullmatch(
            r"[A-Za-z]{2,12}", second
        ):
            candidate = f"{first} {second}"

    normalized = _normal(candidate)
    if len(candidate) > MAX_NAME_LENGTH:
        return None, "too_long"
    if not _NAME_RE.fullmatch(candidate) or len(normalized) < 2:
        return None, "invalid"
    if _has_banned_term(candidate):
        return None, "invalid"

    # منبع اصلی اعتبار: دیتابیس جامع. سپس لقب‌های داخلی و نام‌های لاتین.
    candidate_tokens = candidate.split()
    if (
        persian_names.is_known_name(candidate)
        # شکل بدون فاصله: «سید علی» ↔ «سیدعلی»
        or persian_names.is_known_name("".join(candidate_tokens))
        or persian_names.is_known_name(first)
        # هر واژهٔ نام مرکب باید نام یا پیشوند احترامی معتبر باشد.
        or all(
            persian_names.is_known_name(token)
            or _normal(token) in HONORIFIC_PREFIXES
            or _normal(token) in KNOWN_NAMES
            for token in candidate_tokens
        )
        or _normal(first) in KNOWN_NAMES
        or _normal(first) in NICKNAMES
        or re.fullmatch(r"[A-Za-z]{2,12}(?: [A-Za-z]{2,12})?", candidate)
    ):
        return candidate, None
    return None, "invalid"


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
