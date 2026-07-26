"""Name & Family group game state and category-aware validation."""
import random
from modules.game_points import add

LETTERS = list("ابتثجچحخدذرزسشصضطظعغفقکگلمنوهی")
CATEGORIES = ("نام", "فامیل", "شهر", "میوه", "وسیله", "حیوان", "خواننده")
# Curated real answers; validation is category-specific rather than text-only.
VALID = {
    "نام": {"علی", "امیر", "احمد", "آرمان", "بهرام", "بهزاد", "پارسا", "پرهام", "تینا", "ترانه", "جواد", "حسین", "حامد", "رضا", "رامین", "سارا", "سمیرا", "شادی", "شهرزاد", "صبا", "فاطمه", "فرهاد", "مریم", "محمد", "میلاد", "نازنین", "نگار", "نیما", "یاسمن", "یوسف", "داود", "داریوش", "دانیال"},
    "فامیل": {"احمدی", "اکبری", "امیری", "بهرامی", "پارسا", "پورمحمدی", "جعفری", "حسینی", "رضایی", "رستمی", "سلیمانی", "صادقی", "عباسی", "فرهادی", "کریمی", "محمدی", "مرادی", "نادری", "نوروزی", "یوسفی", "دارایی", "داودی", "دهقان"},
    "شهر": {"اراک", "اردبیل", "اصفهان", "اهواز", "بابل", "بجنورد", "بندرعباس", "تبریز", "تهران", "جهرم", "زاهدان", "رشت", "رامسر", "ساری", "سنندج", "شیراز", "قم", "کرج", "کرمان", "مشهد", "همدان", "یزد", "دهدشت", "دزفول", "دامغان"},
    "میوه": {"آلبالو", "انار", "انگور", "آناناس", "به", "پرتقال", "توت", "خرمالو", "سیب", "شلیل", "طالبی", "گلابی", "گیلاس", "لیمو", "موز", "نارنج", "هندوانه", "هلو", "یوسفی"},
    "وسیله": {"آینه", "اتو", "آچار", "باتری", "پنکه", "تلفن", "چراغ", "چتر", "دفتر", "رادیو", "ساعت", "صندلی", "قفل", "قیچی", "کامپیوتر", "کوله", "لپتاپ", "مداد", "میز", "هدفون", "یخچال", "دستکش", "دوربین", "دریل"},
    "حیوان": {"اسب", "آهو", "ببر", "پلنگ", "پنگوئن", "تمساح", "جغد", "خرس", "روباه", "زرافه", "سگ", "شیر", "فیل", "گربه", "گوسفند", "مار", "میمون", "نهنگ", "یوزپلنگ", "دارکوب", "دلفین", "دال"},
    "خواننده": {"ابی", "احسان خواجه امیری", "بهنام بانی", "حمید هیراد", "رضا صادقی", "شادمهر", "محسن چاوشی", "محسن یگانه", "مهدی احمدوند", "گوگوش", "همایون شجریان", "یاس", "داریوش اقبالی", "داریوش"},
}
_ACTIVE = {}


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id):
    if chat_id in _ACTIVE:
        return None
    state = {"letter": random.SystemRandom().choice(LETTERS), "answers": {}}
    _ACTIVE[chat_id] = state
    return dict(state)


def _normalize(value):
    return value.strip().replace("ي", "ی").replace("ك", "ک").replace("آ", "ا").replace("‌", " ")


def submit(chat_id, user_id, name, text):
    state = _ACTIVE.get(chat_id)
    if not state:
        return None
    parts = [part.strip() for part in text.replace("|", "\n").replace("،", "\n").splitlines() if part.strip()]
    if len(parts) != len(CATEGORIES):
        return None
    letter = state["letter"]
    valid = 0
    for category, answer in zip(CATEGORIES, parts):
        normalized = _normalize(answer)
        valid_answers = {_normalize(item) for item in VALID[category]}
        if normalized.startswith(letter) and normalized in valid_answers:
            valid += 1
    # ساختار کامل پاسخ، شرکت در بازی محسوب می‌شود؛ فقط بخش‌های معتبر امتیاز می‌گیرند.
    points = valid * 10
    state["answers"][str(user_id)] = {"user_id": str(user_id), "name": name, "points": points}
    add(chat_id, user_id, name, points)
    return points


def finish(chat_id):
    state = _ACTIVE.pop(chat_id, None)
    if not state:
        return []
    return sorted(state["answers"].values(), key=lambda item: item["points"], reverse=True)
