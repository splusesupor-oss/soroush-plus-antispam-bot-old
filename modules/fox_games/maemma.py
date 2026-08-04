"""🧩 بازی معما — حدس کلمه/عبارت از روی ایموجی‌ها.

هر کاربر در هر گروه سشنِ مستقل خودش را دارد (کلید ``(chat_id, user_id)``).
تنها کسی که معما را شروع کرده می‌تواند به آن پاسخ دهد؛ پاسخ‌های دیگران
نه امتیاز می‌دهد و نه معمای صاحبش را می‌بندد.

تکرار معما برای یک کاربر با ``economy/game_progress`` (به‌تفکیک گروه و
کاربر) جلوگیری می‌شود؛ در سطح گروه هم چند معمای اخیر کنار گذاشته می‌شوند
تا بقیه جواب را ندیده باشند.

جایزه: ۳ سکه برنز (از جدول `economy.rewards`). reference یکتا و ماندگار
تضمین می‌کند هر معما فقط یک بار سکه بدهد.
"""
import asyncio
import random
import time

from economy import rewards as _rewards
from modules.fox_games.maemma_puzzles import PUZZLES
from modules.fox_games.session_core import (
    log,
    log_error,
    normalize_text,
    to_persian_digits,
)

GAME = "maemma"
COMMAND = "معما"
TIMEOUT_SECONDS = 40
REWARD = 3

# چند معمای اخیرِ گروه کنار گذاشته می‌شوند تا تازه‌واردها معماهایی که
# همین حالا جواب داده شده را نگیرند.
RECENT_WINDOW = 15

_ACTIVE = {}          # (chat_id, user_id) -> state
_TASKS = {}           # (chat_id, user_id) -> timer task
_RANDOM = random.SystemRandom()
_FALLBACK_TOKENS = 0


def _next_token():
    """توکن یکتا و ماندگار پس از ری‌استارت (برای reference جایزه)."""
    global _FALLBACK_TOKENS
    try:
        return _rewards.round_id()
    except Exception:
        _FALLBACK_TOKENS += 1
        return _FALLBACK_TOKENS


def _key(chat_id, user_id):
    return (str(chat_id), str(user_id))


def _norm(value):
    return normalize_text(value).replace(" ", "")


def _accepted(state):
    values = {_norm(state["answer"])}
    values |= {_norm(a) for a in state.get("aliases", ())}
    return {v for v in values if v}


def is_active(chat_id, user_id=None):
    """با user_id یعنی «آیا همین کاربر معما دارد»؛ بدون آن یعنی گروه."""
    if user_id is not None:
        return _key(chat_id, user_id) in _ACTIVE
    chat = str(chat_id)
    return any(k[0] == chat for k in _ACTIVE)


def active_state(chat_id, user_id):
    state = _ACTIVE.get(_key(chat_id, user_id))
    return dict(state) if state else None


def _pick(chat_id, user_id, seen):
    from economy import game_progress as _gp
    recent = set(_gp.recent(chat_id, GAME))
    remaining = [p for p in PUZZLES if p[1] not in seen]
    if not remaining:
        return None
    preferred = [p for p in remaining if p[1] not in recent]
    pool = preferred or remaining
    return _RANDOM.choice(pool)


def start(chat_id, user_id, logger=None):
    """معمایی می‌دهد که این کاربر هنوز ندیده است.

    خروجی state یا None (اگر همین کاربر معما دارد / بانک خالی).
    """
    key = _key(chat_id, user_id)
    if key in _ACTIVE:
        return None

    from economy import game_progress as _gp
    seen = _gp.seen(chat_id, user_id, GAME)
    if len(seen) >= len(PUZZLES):
        _gp.start_new_cycle(chat_id, user_id, GAME)
        seen = _gp.seen(chat_id, user_id, GAME)

    picked = _pick(chat_id, user_id, seen)
    if picked is None:
        return None

    emoji, answer, aliases = picked
    _gp.mark_seen(chat_id, user_id, GAME, answer)
    _gp.mark_recent(chat_id, GAME, answer, RECENT_WINDOW)

    state = {
        "emoji": emoji,
        "answer": answer,
        "aliases": tuple(aliases),
        "token": _next_token(),
        "user_id": user_id,
        "chat_id": chat_id,
        "created_at": time.monotonic(),
    }
    _ACTIVE[key] = state
    log(logger, f"MAEMMA START chat_id={chat_id} user_id={user_id} "
                f"session_id={state['token']} answer={answer!r}")
    return dict(state)


def answer(chat_id, user_id, name, text, logger=None):
    """فقط صاحب معما می‌تواند پاسخ بدهد؛ سشن بسته و دادهٔ برنده برمی‌گردد.

    خروجی: دیکشنری {answer, token, user_id, name} یا None.
    پرداخت توسط روتر (از راه `_coins`) انجام می‌شود تا در تست با
    `bot.award_coins` قابل رهگیری باشد.
    """
    key = _key(chat_id, user_id)
    state = _ACTIVE.get(key)
    if not state:
        return None
    if _norm(text) not in _accepted(state):
        return None

    token = state["token"]
    answer_value = state["answer"]
    _cancel_task(key)
    _ACTIVE.pop(key, None)
    log(logger, f"MAEMMA CORRECT chat_id={chat_id} user_id={user_id} "
                f"answer={answer_value!r}")
    return {
        "answer": answer_value,
        "token": token,
        "user_id": user_id,
        "name": name,
    }


def finish(chat_id, token=None, user_id=None, logger=None):
    """پایان زمان: فقط سشنِ همان کاربر (با گارد توکن) بسته می‌شود.

    اگر از درونِ خودِ تایمر فراخوانی شود، تسکِ جاری را cancel نمی‌کند تا
    پاسخِ timeout قطع نشود.
    """
    key = _key(chat_id, user_id)
    state = _ACTIVE.get(key)
    if not state or (token is not None and state["token"] != token):
        return None
    task = _TASKS.get(key)
    current = asyncio.current_task()
    if task is not None and task is not current and not task.done():
        task.cancel()
    _TASKS.pop(key, None)
    _ACTIVE.pop(key, None)
    log(logger, f"MAEMMA TIMEOUT chat_id={chat_id} user_id={user_id}")
    return state["answer"]


def _cancel_task(key):
    task = _TASKS.pop(key, None)
    if task is not None and not task.done():
        task.cancel()


async def run_timeout(chat_id, user_id, token, on_timeout, logger=None,
                      timeout=None):
    limit = TIMEOUT_SECONDS if timeout is None else timeout
    try:
        await asyncio.sleep(limit)
    except asyncio.CancelledError:
        raise
    finally:
        answer_value = finish(chat_id, token, user_id, logger)
        if answer_value:
            try:
                await on_timeout(answer_value)
            except Exception:
                pass


def schedule(chat_id, user_id, token, on_timeout, logger=None, timeout=None):
    key = _key(chat_id, user_id)
    _cancel_task(key)
    loop = asyncio.get_running_loop()
    task = loop.create_task(run_timeout(
        chat_id, user_id, token, on_timeout, logger, timeout))
    _TASKS[key] = task

    def _cleanup(done):
        if _TASKS.get(key) is done:
            _TASKS.pop(key, None)

    task.add_done_callback(_cleanup)
    return task


def reset_all(chat_id=None, user_id=None):
    """پاک‌سازی کامل — برای تست و ری‌استارت."""
    global _FALLBACK_TOKENS
    if chat_id is None:
        for task in list(_TASKS.values()):
            if not task.done():
                task.cancel()
        _TASKS.clear()
        _ACTIVE.clear()
        return
    if user_id is not None:
        key = _key(chat_id, user_id)
        _cancel_task(key)
        _ACTIVE.pop(key, None)
        return
    chat = str(chat_id)
    for key in [k for k in _ACTIVE if k[0] == chat]:
        _cancel_task(key)
        _ACTIVE.pop(key, None)
