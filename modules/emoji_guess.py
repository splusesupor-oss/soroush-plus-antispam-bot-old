"""Guess the Emoji game state."""
import random
from itertools import count
from modules.game_points import add

PUZZLES = [('🍕🐢', 'لاک\u200cپشت\u200cهای نینجا'), ('🕷️👨', 'مرد عنکبوتی'), ('🦁👑', 'شیرشاه'), ('❄️👸', 'فروزن'), ('🐼🥋', 'پاندای کونگ\u200cفوکار'), ('🚗⚡', 'ماشین\u200cها'), ('🤖🗑️', 'وال ای'), ('🧙💍', 'ارباب حلقه\u200cها'), ('🦇👨', 'بتمن'), ('🧞\u200d♂️🪔', 'علاءالدین'), ('🦖🏝️', 'پارک ژوراسیک'), ('👻🚫', 'شکارچیان روح'), ('🐠🔎', 'در جستجوی نمو'), ('🌙🚀', 'سفر به ماه'), ('⚽🥅', 'فوتبال'), ('🏀⛹️', 'بسکتبال'), ('🏐🙌', 'والیبال'), ('☕🌧️', 'قهوه'), ('🍕🍕', 'پیتزا'), ('🍔🍟', 'همبرگر'), ('🍫🍬', 'شکلات'), ('🍦❄️', 'بستنی'), ('🎂🎉', 'تولد'), ('🎁✨', 'هدیه'), ('🏫📚', 'مدرسه'), ('🎓🏫', 'دانشگاه'), ('📚☕', 'کتاب'), ('🎵🎧', 'موسیقی'), ('🎸🎶', 'گیتار'), ('🎹🎼', 'پیانو'), ('🎤🎙️', 'خواننده'), ('🍿🎬', 'سینما'), ('✈️🧳', 'سفر'), ('✈️☁️', 'هواپیما'), ('🚂🛤️', 'قطار'), ('🚌🛣️', 'اتوبوس'), ('🚲🌳', 'دوچرخه'), ('🚗💨', 'ماشین'), ('🏠🔑', 'خانه'), ('🛏️😴', 'خواب'), ('☔🌧️', 'باران'), ('❄️☃️', 'برف'), ('☀️🍉', 'تابستان'), ('🍂🌳', 'پاییز'), ('🌸🌱', 'بهار'), ('❄️🧣', 'زمستان'), ('🌙⭐', 'شب'), ('☀️😎', 'خورشید'), ('🌙🌕', 'ماه'), ('⭐🌌', 'ستاره'), ('🔥🪵', 'آتش'), ('🌊🐚', 'دریا'), ('🏔️❄️', 'کوه'), ('🌲🌳', 'جنگل'), ('🐈🐟', 'گربه'), ('🐕🦴', 'سگ'), ('🐬🌊', 'دلفین'), ('🐧❄️', 'پنگوئن'), ('🦋🌸', 'پروانه'), ('🐝🌼', 'زنبور'), ('🌹🌸', 'گل'), ('🤝😊', 'دوستی'), ('😂🤣', 'خنده'), ('😢💔', 'غم'), ('❤️🌹', 'عشق'), ('📶🌐', 'اینترنت'), ('📱✨', 'گوشی'), ('🔋📱', 'شارژ گوشی'), ('🎧🎵', 'هدفون'), ('💻⌨️', 'لپ تاپ'), ('🎮🕹️', 'بازی'), ('📷🤳', 'عکس'), ('🤳📱', 'سلفی'), ('🍳🥚', 'آشپزی'), ('🎨🖌️', 'نقاشی'), ('📝✏️', 'نوشتن'), ('⏰⌛', 'زمان'), ('🚦🚗', 'ترافیک'), ('🛒🛍️', 'خرید'), ('🔑🚪', 'کلید'), ('⌚⏰', 'ساعت'), ('👓📖', 'عینک'), ('☔🌂', 'چتر'), ('🎒📚', 'کوله پشتی'), ('✏️📄', 'مداد'), ('📒🖊️', 'دفتر'), ('🧁🍰', 'شیرینی'), ('🍰🎂', 'کیک'), ('🏖️☀️', 'ساحل'), ('🚀🌌', 'فضا')]
_ACTIVE = {}
_TOKENS = count(1)
ALIASES = {
    "لاک‌پشت‌های نینجا": ("teenage mutant ninja turtles", "ninja turtles"),
    "مرد عنکبوتی": ("spider man", "spiderman"),
    "شیرشاه": ("lion king",), "فروزن": ("frozen",),
    "پاندای کونگ‌فوکار": ("kung fu panda",), "ماشین‌ها": ("cars",),
    "وال ای": ("wall e", "walle"), "ارباب حلقه‌ها": ("lord of the rings",),
    "بتمن": ("batman",), "علاءالدین": ("aladdin",),
    "پارک ژوراسیک": ("jurassic park",), "شکارچیان روح": ("ghostbusters",),
    "در جستجوی نمو": ("finding nemo",), "سفر به ماه": ("trip to the moon",),
    "فوتبال": ("football",), "بسکتبال": ("basketball",), "والیبال": ("volleyball",),
    "قهوه": ("coffee",), "پیتزا": ("pizza",), "همبرگر": ("hamburger",),
    "شکلات": ("chocolate",), "بستنی": ("ice cream",), "تولد": ("birthday",),
    "هدیه": ("gift",), "مدرسه": ("school",), "دانشگاه": ("university",),
    "کتاب": ("book",), "موسیقی": ("music",), "گیتار": ("guitar",), "پیانو": ("piano",),
    "خواننده": ("singer",), "سینما": ("cinema",), "سفر": ("travel",), "هواپیما": ("airplane",),
    "قطار": ("train",), "اتوبوس": ("bus",), "دوچرخه": ("bicycle",), "ماشین": ("car",),
    "خانه": ("home",), "خواب": ("sleep",), "باران": ("rain",), "برف": ("snow",),
}


def _norm(text):
    return str(text).strip().lower().replace("‌", " ").replace("ي", "ی").replace("ك", "ک")


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id):
    if chat_id in _ACTIVE:
        return None
    emoji, answer = random.SystemRandom().choice(PUZZLES)
    _ACTIVE[chat_id] = {
        "emoji": emoji,
        "answer": answer,
        "token": next(_TOKENS),
    }
    return dict(_ACTIVE[chat_id])


def answer(chat_id, user_id, name, text):
    state = _ACTIVE.get(chat_id)
    if not state:
        return None
    accepted = {_norm(state["answer"])} | {_norm(value) for value in ALIASES.get(state["answer"], ())}
    if _norm(text) not in accepted:
        return None
    _ACTIVE.pop(chat_id, None)
    add(chat_id, user_id, name, 20)
    return state["answer"]


def finish(chat_id, token=None):
    state = _ACTIVE.get(chat_id)
    if not state or (token is not None and state["token"] != token):
        return None
    _ACTIVE.pop(chat_id, None)
    return state["answer"]
