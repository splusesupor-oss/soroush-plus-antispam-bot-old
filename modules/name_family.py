"""Name & Family group game state and category-aware validation."""
import random
from modules.game_points import add

LETTERS = ("ا", "ب", "پ", "ت", "ث", "ج", "چ", "ح", "خ", "د", "ذ", "ر", "ز", "ژ", "س", "ش", "ص", "ض", "ط", "ظ", "ع", "غ", "ف", "ق", "ک", "گ", "ل", "م", "ن", "و", "ه", "ی")
CATEGORIES = ("نام", "فامیل", "شهر", "میوه", "وسیله", "حیوان", "خواننده")
# Curated real answers; validation is category-specific rather than text-only.
VALID = {
    "نام": {"علی", "امیر", "احمد", "آرمان", "بهرام", "بهزاد", "پارسا", "پرهام", "تینا", "ترانه", "جواد", "حسین", "حامد", "رضا", "رامین", "سارا", "سمیرا", "شادی", "شهرزاد", "صبا", "فاطمه", "فرهاد", "فریبا", "مریم", "محمد", "میلاد", "نازنین", "نگار", "نیما", "یاسمن", "یوسف", "داود", "داریوش", "دانیال"},
    "فامیل": {"احمدی", "اکبری", "امیری", "بهرامی", "پارسا", "پورمحمدی", "جعفری", "حسینی", "رضایی", "رستمی", "سلیمانی", "صادقی", "عباسی", "فرهادی", "فری", "کریمی", "محمدی", "مرادی", "نادری", "نوروزی", "یوسفی", "دارایی", "داودی", "دهقان"},
    "شهر": {"اراک", "اردبیل", "اصفهان", "اهواز", "بابل", "بجنورد", "بندرعباس", "تبریز", "تهران", "جهرم", "زاهدان", "رشت", "رامسر", "ساری", "سنندج", "شیراز", "قم", "کرج", "کرمان", "مشهد", "همدان", "یزد", "دهدشت", "دزفول", "دامغان", "فیروزکوه", "فیروز کوه", "فردوس"},
    "میوه": {"آلبالو", "انار", "انگور", "آناناس", "به", "پرتقال", "توت", "خرمالو", "سیب", "شلیل", "طالبی", "گلابی", "گیلاس", "لیمو", "موز", "نارنج", "هندوانه", "هلو", "یوسفی", "فندق", "فراوله"},
    "وسیله": {"آینه", "اتو", "آچار", "باتری", "پنکه", "تلفن", "چراغ", "چتر", "دفتر", "رادیو", "ساعت", "صندلی", "قفل", "قیچی", "کامپیوتر", "کوله", "لپتاپ", "مداد", "میز", "هدفون", "یخچال", "دستکش", "دوربین", "دریل", "فرغون", "فلاسک"},
    "حیوان": {"اسب", "آهو", "ببر", "پلنگ", "پنگوئن", "تمساح", "جغد", "خرس", "روباه", "زرافه", "سگ", "شیر", "فیل", "گربه", "گوسفند", "مار", "میمون", "نهنگ", "یوزپلنگ", "دارکوب", "دلفین", "دال", "فیل"},
    "خواننده": {"ابی", "احسان خواجه امیری", "بهنام بانی", "حمید هیراد", "رضا صادقی", "شادمهر", "محسن چاوشی", "محسن یگانه", "مهدی احمدوند", "گوگوش", "همایون شجریان", "یاس", "داریوش اقبالی", "داریوش", "فرهاد", "فرهاد مهراد"},
}
_ACTIVE = {}
_REMAINING_LETTERS = {}


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id):
    if chat_id in _ACTIVE:
        return None
    remaining = _REMAINING_LETTERS.get(chat_id)
    if not remaining:
        remaining = list(LETTERS)
        random.SystemRandom().shuffle(remaining)
        _REMAINING_LETTERS[chat_id] = remaining
    state = {"letter": remaining.pop(), "answers": {}}
    _ACTIVE[chat_id] = state
    return dict(state)


def _normalize(value):
    return value.strip().replace("ي", "ی").replace("ك", "ک").replace("آ", "ا").replace("‌", " ")


def submit(chat_id, user_id, name, text):
    state = _ACTIVE.get(chat_id)
    if not state:
        return None
    parts = [part.strip() for part in text.replace("|", "\n").replace("،", "\n").splitlines() if part.strip()]
    # پاسخ‌های رایج «نام: داود» و فرم دوخطیِ عنوان/پاسخ را هم پشتیبانی می‌کنیم.
    if len(parts) == len(CATEGORIES) * 2 and all(
        _normalize(parts[index * 2]) == _normalize(category)
        for index, category in enumerate(CATEGORIES)
    ):
        parts = parts[1::2]
    if len(parts) != len(CATEGORIES):
        return None

    letter = _normalize(state["letter"])
    invalid_answers = {"نمیدونم", "نمی دونم", "نمیدانم", "ندارم", "هیچی", "نمیگم"}
    valid = 0
    for category, answer in zip(CATEGORIES, parts):
        normalized = _normalize(answer)
        category_label = _normalize(category)
        if normalized.startswith(category_label):
            normalized = normalized[len(category_label):].lstrip(":：- ").strip()
        valid_answers = {_normalize(item) for item in VALID[category]}
        # فقط پاسخ واقعی همان دسته با حرف انتخاب‌شده 10 امتیاز می‌گیرد.
        if (
            len(normalized) > 1
            and normalized.startswith(letter)
            and normalized not in invalid_answers
            and normalized in valid_answers
        ):
            valid += 1
    points = valid * 10
    state["answers"][str(user_id)] = {"user_id": str(user_id), "name": name, "points": points}
    add(chat_id, user_id, name, points)
    return points


def finish(chat_id):
    state = _ACTIVE.pop(chat_id, None)
    if not state:
        return []
    return sorted(state["answers"].values(), key=lambda item: item["points"], reverse=True)
