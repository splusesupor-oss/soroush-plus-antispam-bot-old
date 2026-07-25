"""Guess the Emoji game state."""
import random
from itertools import count
from modules.game_points import add

PUZZLES = [
    ("🍕🐢", "لاک‌پشت‌های نینجا"), ("🕷️👨", "مرد عنکبوتی"),
    ("🦁👑", "شیرشاه"), ("❄️👸", "فروزن"), ("🐼🥋", "پاندای کونگ‌فوکار"),
    ("🚗⚡", "ماشین‌ها"), ("🤖🗑️", "وال ای"), ("🧙💍", "ارباب حلقه‌ها"),
    ("🦇👨", "بتمن"), ("🧞‍♂️🪔", "علاءالدین"), ("🦖🏝️", "پارک ژوراسیک"),
    ("👻🚫", "شکارچیان روح"), ("🐠🔎", "در جستجوی نمو"), ("🌙🚀", "سفر به ماه"),
]
_ACTIVE = {}
_TOKENS = count(1)


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
    if not state or _norm(text) != _norm(state["answer"]):
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
