"""Thirty-second country flag guessing game using Unicode flag images."""
import random
from itertools import count

COUNTRIES = (
    ("🇮🇷", "ایران", ("iran",)), ("🇯🇵", "ژاپن", ("japan",)),
    ("🇫🇷", "فرانسه", ("france",)), ("🇩🇪", "آلمان", ("germany",)),
    ("🇮🇹", "ایتالیا", ("italy",)), ("🇪🇸", "اسپانیا", ("spain",)),
    ("🇧🇷", "برزیل", ("brazil",)), ("🇨🇦", "کانادا", ("canada",)),
    ("🇦🇺", "استرالیا", ("australia",)), ("🇮🇳", "هند", ("india",)),
    ("🇨🇳", "چین", ("china",)), ("🇰🇷", "کره جنوبی", ("south korea", "کره‌جنوبی")),
    ("🇹🇷", "ترکیه", ("turkey",)), ("🇸🇦", "عربستان سعودی", ("saudi arabia", "عربستان")),
    ("🇦🇷", "آرژانتین", ("argentina",)), ("🇲🇽", "مکزیک", ("mexico",)),
    ("🇪🇬", "مصر", ("egypt",)), ("🇿🇦", "آفریقای جنوبی", ("south africa",)),
    ("🇳🇴", "نروژ", ("norway",)), ("🇸🇪", "سوئد", ("sweden",)),
    ("🇨🇭", "سوئیس", ("switzerland",)), ("🇬🇷", "یونان", ("greece",)),
    ("🇵🇹", "پرتغال", ("portugal",)), ("🇳🇱", "هلند", ("netherlands",)),
    ("🇹🇭", "تایلند", ("thailand",)), ("🇮🇩", "اندونزی", ("indonesia",)),
    ("🇳🇬", "نیجریه", ("nigeria",)), ("🇲🇦", "مراکش", ("morocco",)),
)
_ACTIVE = {}
_LAST_COUNTRY = {}
_TOKENS = count(1)


def _norm(value):
    return " ".join(str(value or "").strip().lower().replace("‌", " ").replace("ي", "ی").replace("ك", "ک").split())


def is_active(chat_id):
    return chat_id in _ACTIVE


def start(chat_id):
    if chat_id in _ACTIVE:
        return None
    candidates = [country for country in COUNTRIES if country[1] != _LAST_COUNTRY.get(str(chat_id))]
    flag, answer, aliases = random.SystemRandom().choice(candidates or list(COUNTRIES))
    state = {"flag": flag, "answer": answer, "aliases": aliases, "token": next(_TOKENS)}
    _ACTIVE[chat_id] = state
    _LAST_COUNTRY[str(chat_id)] = answer
    return dict(state)


def answer(chat_id, text):
    state = _ACTIVE.get(chat_id)
    if not state:
        return None
    accepted = {_norm(state["answer"])} | {_norm(alias) for alias in state["aliases"]}
    if _norm(text) not in accepted:
        return None
    _ACTIVE.pop(chat_id, None)
    return state["answer"]


def finish(chat_id, token=None):
    state = _ACTIVE.get(chat_id)
    if not state or (token is not None and state["token"] != token):
        return None
    _ACTIVE.pop(chat_id, None)
    return state["answer"]
