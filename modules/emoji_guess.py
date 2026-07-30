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

# ---------------------------------------------------------------------------
# تاریخچهٔ معماهای دیده‌شده، به تفکیک «کاربر».
#
# پیش از این هیچ تاریخچه‌ای وجود نداشت و انتخاب کاملاً تصادفی بود، بنابراین
# یک کاربر می‌توانست با اجرای دوبارهٔ دستور همان ایموجی را بگیرد و از روی
# پاسخ قبلی سکه بگیرد. اکنون هر کاربر تا وقتی همهٔ معماها را ندیده، هرگز
# معمای تکراری دریافت نمی‌کند.
#
# این ساختار فقط متعلق به همین بازی است و با تایمر، سکه یا بازی‌های دیگر
# هیچ اشتراکی ندارد.
# ---------------------------------------------------------------------------
_SEEN_BY_USER = {}
_RANDOM = random.SystemRandom()

EXHAUSTED_MESSAGE = (
    "تمام ایموجی‌ها را قبلاً حدس زده‌اید، "
    "برای جلوگیری از سوءاستفاده از بازی‌های دیگر استفاده کنید."
)


def _user_key(user_id):
    return str(user_id)


def seen_count(user_id):
    """تعداد معماهایی که این کاربر تا کنون دیده است."""
    return len(_SEEN_BY_USER.get(_user_key(user_id), ()))


def remaining_count(user_id):
    """تعداد معماهای باقی‌مانده برای این کاربر."""
    return max(len(PUZZLES) - seen_count(user_id), 0)


def is_exhausted(user_id):
    """آیا این کاربر همهٔ معماها را دیده است."""
    return remaining_count(user_id) == 0


def reset_user(user_id=None):
    """تاریخچهٔ یک کاربر (یا همهٔ کاربران) را پاک می‌کند."""
    if user_id is None:
        _SEEN_BY_USER.clear()
        return
    _SEEN_BY_USER.pop(_user_key(user_id), None)


def reset_all():
    """پاک‌سازی کامل — برای تست."""
    _ACTIVE.clear()
    _SEEN_BY_USER.clear()


def _norm(text):
    return str(text).strip().lower().replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id, user_id=None):
    """بازی تازه شروع می‌کند و معمایی می‌دهد که این کاربر ندیده است.

    ``None`` یعنی شروع نشد: یا بازی دیگری در همین چت فعال است، یا این کاربر
    همهٔ معماها را دیده. برای تفکیک این دو از ``is_exhausted`` استفاده کنید.
    """
    if chat_id in _ACTIVE:
        return None
    if user_id is None:
        user_id = chat_id

    key = _user_key(user_id)
    seen = _SEEN_BY_USER.setdefault(key, set())
    remaining = [item for item in PUZZLES if item[1] not in seen]
    if not remaining:
        # همهٔ معماها برای این کاربر مصرف شده است.
        return None

    emoji, answer = _RANDOM.choice(remaining)
    seen.add(answer)
    _ACTIVE[chat_id] = {
        "emoji": emoji,
        "answer": answer,
        "token": next(_TOKENS),
        "user_id": user_id,
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
