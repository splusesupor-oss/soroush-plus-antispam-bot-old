"""Name & Family group game state and strict category-aware validation."""
import random
import re

from modules.game_points import add

LETTERS = (
    "ا", "ب", "پ", "ت", "ث", "ج", "چ", "ح", "خ", "د", "ذ", "ر", "ز", "ژ",
    "س", "ش", "ص", "ض", "ط", "ظ", "ع", "غ", "ف", "ق", "ک", "گ", "ل", "م",
    "ن", "و", "ه", "ی",
)
CATEGORIES = ("نام", "فامیل", "شهر", "میوه", "وسیله", "حیوان", "خواننده")

# Curated answers are deliberately category-specific. A matching first letter alone is never enough.
VALID = {
    "نام": {"علی", "امیر", "احمد", "آرمان", "بهرام", "بهزاد", "پارسا", "پرهام", "تینا", "ترانه", "جواد", "حسین", "حامد", "رضا", "رامین", "سارا", "سمیرا", "شادی", "شهرزاد", "صبا", "فاطمه", "فرهاد", "فریبا", "مریم", "محمد", "میلاد", "نازنین", "نگار", "نیما", "یاسمن", "یوسف", "داود", "داریوش", "دانیال"},
    "فامیل": {"احمدی", "اکبری", "امیری", "بهرامی", "پارسا", "پورمحمدی", "جعفری", "حسینی", "رضایی", "رستمی", "سلیمانی", "صادقی", "عباسی", "فرهادی", "فری", "کریمی", "محمدی", "مرادی", "نادری", "نوروزی", "یوسفی", "دارایی", "داودی", "دهقان"},
    "شهر": {"اراک", "اردبیل", "اصفهان", "اهواز", "بابل", "بجنورد", "بندرعباس", "تبریز", "تهران", "جهرم", "زاهدان", "رشت", "رامسر", "ساری", "سنندج", "شیراز", "قم", "کرج", "کرمان", "مشهد", "همدان", "یزد", "دهدشت", "دزفول", "دامغان", "فیروزکوه", "فیروز کوه", "فردوس"},
    "میوه": {"آلبالو", "انار", "انگور", "آناناس", "به", "پرتقال", "توت", "خرمالو", "سیب", "شلیل", "طالبی", "گلابی", "گیلاس", "لیمو", "موز", "نارنج", "هندوانه", "هلو", "یوسفی", "فندق", "فراوله"},
    "وسیله": {"آینه", "اتو", "آچار", "باتری", "پنکه", "تلفن", "چراغ", "چتر", "دفتر", "رادیو", "ساعت", "صندلی", "قفل", "قیچی", "کامپیوتر", "کوله", "لپتاپ", "مداد", "میز", "هدفون", "یخچال", "دستکش", "دوربین", "دریل", "فرغون", "فلاسک"},
    "حیوان": {"اسب", "آهو", "ببر", "پلنگ", "پنگوئن", "تمساح", "جغد", "خرس", "روباه", "زرافه", "سگ", "شیر", "فیل", "گربه", "گوسفند", "مار", "میمون", "نهنگ", "یوزپلنگ", "دارکوب", "دلفین", "دال"},
    "خواننده": {"ابی", "احسان خواجه امیری", "بهنام بانی", "حمید هیراد", "رضا صادقی", "شادمهر", "محسن چاوشی", "محسن یگانه", "مهدی احمدوند", "گوگوش", "همایون شجریان", "یاس", "داریوش اقبالی", "داریوش", "فرهاد", "فرهاد مهراد"},
}

_INVALID_ANSWERS = frozenset({"نمیدونم", "نمی دونم", "نمیدانم", "ندارم", "هیچی", "نمیگم"})
# Spaces are allowed for compound names; digits, Latin letters, emoji and punctuation are rejected.
_VALID_TEXT = re.compile(r"^[آ-یءئؤة\s]+$")
_ACTIVE = {}
_REMAINING_LETTERS = {}
_ROUND_SEQUENCE = 0


def _normalize(value):
    return (
        str(value or "").strip().lower()
        .replace("ي", "ی").replace("ك", "ک").replace("آ", "ا")
        .replace("‌", " ")
    )


VALID_NORMALIZED = {
    category: frozenset(_normalize(answer) for answer in answers)
    for category, answers in VALID.items()
}


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id):
    global _ROUND_SEQUENCE
    if chat_id in _ACTIVE:
        return None
    remaining = _REMAINING_LETTERS.get(chat_id)
    if not remaining:
        remaining = list(LETTERS)
        random.SystemRandom().shuffle(remaining)
        _REMAINING_LETTERS[chat_id] = remaining
    _ROUND_SEQUENCE += 1
    state = {
        "round_id": _ROUND_SEQUENCE,
        "letter": remaining.pop(),
        "answers": {},
    }
    _ACTIVE[chat_id] = state
    return {"round_id": state["round_id"], "letter": state["letter"], "answers": {}}


def _parse_answers(text):
    parts = [
        part.strip()
        for part in str(text or "").replace("|", "\n").replace("،", "\n").splitlines()
        if part.strip()
    ]
    # Supports alternating category/value input as well as seven raw answer lines.
    if len(parts) == len(CATEGORIES) * 2 and all(
        _normalize(parts[index * 2]) == _normalize(category)
        for index, category in enumerate(CATEGORIES)
    ):
        parts = parts[1::2]
    return parts if len(parts) == len(CATEGORIES) else None


def _validate_answer(category, letter, answer):
    """Returns True only for a real answer in the requested category."""
    normalized = _normalize(answer)
    category_label = _normalize(category)
    if normalized.startswith(category_label):
        normalized = normalized[len(category_label):].lstrip(":：- ").strip()
    if (
        len(normalized) < 2
        or not _VALID_TEXT.fullmatch(normalized)
        or normalized in _INVALID_ANSWERS
        or not normalized.startswith(_normalize(letter))
    ):
        return False
    return normalized in VALID_NORMALIZED[category]


def submit(chat_id, user_id, name, text):
    state = _ACTIVE.get(chat_id)
    if not state:
        return None
    user_key = str(user_id)
    # A round accepts exactly one score per participant. This prevents the persistent
    # game score from being added twice while the round ranking is overwritten.
    existing = state["answers"].get(user_key)
    if existing is not None:
        return existing["points"]

    parts = _parse_answers(text)
    if parts is None:
        return None
    valid_parts = sum(
        _validate_answer(category, state["letter"], answer)
        for category, answer in zip(CATEGORIES, parts)
    )
    points = valid_parts * 10
    state["answers"][user_key] = {
        "user_id": user_key,
        "name": name,
        "points": points,
        "round_id": state["round_id"],
    }
    add(chat_id, user_id, name, points)
    return points


def finish(chat_id):
    state = _ACTIVE.pop(chat_id, None)
    if not state:
        return []
    return sorted(
        state["answers"].values(),
        key=lambda item: item["points"],
        reverse=True,
    )
