"""🧛 خون‌آشام — یک نفر مخفیانه خون‌آشام است؛ بقیه باید او را حدس بزنند."""
import asyncio
import random

from modules.fox_games.session_core import (
    SessionStore,
    display_name,
    log,
    log_error,
    parse_int,
    to_persian_digits,
    username_tag,
)

GAME_NAME = "vampire"
COMMAND = "خون آشام"
JOIN_WORD = "شرکت"

MIN_PLAYERS = 4
MAX_PLAYERS = 5
JOIN_SECONDS = 60
GUESS_SECONDS = 50
WINNER_COINS = 7

_STORE = SessionStore(GAME_NAME)
_RANDOM = random.SystemRandom()

ALREADY_RUNNING = "🧛 بازی خون‌آشام همین حالا در جریان است."
NOT_ENOUGH = "🧛 تعداد شرکت‌کننده کافی نبود؛ بازی لغو شد."
ROLE_MESSAGE = "🧛 شما خون‌آشام هستید.\n\nتا پایان بازی چیزی نگویید."
CHOSEN_MESSAGE = "خون‌آشام انتخاب شد."


def is_active(chat_id):
    return _STORE.is_active(chat_id)


def phase(chat_id):
    session = _STORE.get(chat_id)
    return session.get("phase") if session else None


def start(chat_id, logger=None):
    session = _STORE.create(chat_id, {
        "phase": "joining",
        "players": [],
        "ids": set(),
        "vampire": None,
        "guessed": set(),
    })
    if session is None:
        log(logger, f"FOX VAMPIRE START BLOCKED chat_id={chat_id} reason=already_active")
        return None
    log(logger, f"FOX VAMPIRE START chat_id={chat_id} session_id={session['session_id']}")
    return dict(session)


def join(chat_id, user_id, user, logger=None):
    """ثبت‌نام. خروجی ``(state, players)``."""
    session = _STORE.get(chat_id)
    if not session or session.get("phase") != "joining":
        return "closed", []
    if user_id in session["ids"]:
        return "duplicate", list(session["players"])
    if len(session["players"]) >= MAX_PLAYERS:
        return "full", list(session["players"])

    player = {
        "user_id": user_id,
        "name": display_name(user),
        "tag": username_tag(user),
    }
    session["ids"].add(user_id)
    session["players"].append(player)
    log(logger, f"FOX VAMPIRE JOIN chat_id={chat_id} user_id={user_id} "
                f"name={player['name']} count={len(session['players'])}")
    return "joined", list(session["players"])


def player_count(chat_id):
    session = _STORE.get(chat_id)
    return len(session["players"]) if session else 0


def is_full(chat_id):
    return player_count(chat_id) >= MAX_PLAYERS


def roster_lines(players):
    """فهرست شماره‌دار بازیکنان با ارقام فارسی."""
    return "\n".join(
        f"{to_persian_digits(index)}. {player['name']}"
        for index, player in enumerate(players, 1)
    )


def choose_vampire(chat_id, logger=None):
    """یک بازیکن را تصادفی خون‌آشام می‌کند. None اگر تعداد کافی نباشد."""
    session = _STORE.get(chat_id)
    if not session or session.get("phase") != "joining":
        return None
    if len(session["players"]) < MIN_PLAYERS:
        log(logger, f"FOX VAMPIRE ABORT chat_id={chat_id} reason=not_enough_players "
                    f"count={len(session['players'])}")
        return None
    index = _RANDOM.randrange(len(session["players"]))
    session["vampire"] = index
    session["phase"] = "guessing"
    vampire = session["players"][index]
    log(logger,
        f"FOX VAMPIRE CHOSEN chat_id={chat_id} session_id={session['session_id']} "
        f"vampire_user_id={vampire['user_id']} number={index + 1}")
    return {
        "number": index + 1,
        "player": dict(vampire),
        "players": list(session["players"]),
    }


def guess(chat_id, user_id, text, logger=None):
    """یک حدس. خروجی ``(state, info)``.

    state در ``{"correct","wrong","not_player","already","is_vampire",
    "bad_number","closed"}``.
    """
    session = _STORE.get(chat_id)
    if not session or session.get("phase") != "guessing":
        return "closed", None
    if user_id not in session["ids"]:
        return "not_player", None

    vampire_index = session["vampire"]
    if session["players"][vampire_index]["user_id"] == user_id:
        log(logger, f"FOX VAMPIRE GUESS BLOCKED chat_id={chat_id} "
                    f"user_id={user_id} reason=is_vampire")
        return "is_vampire", None
    if user_id in session["guessed"]:
        return "already", None

    number = parse_int(text)
    if number is None or not 1 <= number <= len(session["players"]):
        return "bad_number", None

    session["guessed"].add(user_id)
    guesser = next(p for p in session["players"] if p["user_id"] == user_id)
    log(logger, f"FOX VAMPIRE GUESS chat_id={chat_id} user_id={user_id} "
                f"number={number}")

    if number - 1 == vampire_index:
        vampire = dict(session["players"][vampire_index])
        closed = _STORE.close(chat_id, session["session_id"])
        _STORE.cancel_task(chat_id)
        if closed is None:
            return "closed", None
        log(logger,
            f"FOX VAMPIRE WINNER chat_id={chat_id} user_id={user_id} "
            f"name={guesser['name']} coins={WINNER_COINS}")
        return "correct", {
            "guesser": guesser,
            "vampire": vampire,
            "coins": WINNER_COINS,
        }
    return "wrong", {"guesser": guesser, "number": number}


def reveal(chat_id, session_id=None, logger=None):
    """پایان بدون برنده؛ خون‌آشام را برمی‌گرداند."""
    session = _STORE.get(chat_id)
    if not session:
        return None
    vampire = None
    if session.get("vampire") is not None:
        vampire = dict(session["players"][session["vampire"]])
    closed = _STORE.close(chat_id, session_id or session["session_id"])
    _STORE.cancel_task(chat_id)
    if closed is None:
        return None
    log(logger, f"FOX VAMPIRE TIMEOUT chat_id={chat_id} "
                f"session_id={closed['session_id']} "
                f"vampire={vampire['name'] if vampire else None}")
    return vampire


def abandon(chat_id, session_id=None, logger=None):
    session = _STORE.close(chat_id, session_id)
    _STORE.cancel_task(chat_id)
    return bool(session)


def format_reveal(vampire):
    """نام نمایشی و در صورت وجود، یوزرنیم را کنارش نشان می‌دهد.

    اگر نام نمایشی خودش همان یوزرنیم باشد (کاربری که Display Name ندارد)،
    دوباره تکرار نمی‌شود.
    """
    name = vampire["name"]
    tag = vampire.get("tag") or ""
    suffix = f" ({tag})" if tag and tag != name else ""
    return f"⏰ زمان تمام شد.\n\n🧛 خون‌آشام:\n\n{name}{suffix}"


async def run_game(chat_id, session_id, callbacks, logger=None,
                   join_seconds=None, guess_seconds=None):
    """چرخهٔ کامل بازی؛ افشای خون‌آشام همیشه تضمین شده است."""
    join_wait = JOIN_SECONDS if join_seconds is None else join_seconds
    guess_wait = GUESS_SECONDS if guess_seconds is None else guess_seconds
    revealed = False
    try:
        waited = 0.0
        step = 0.05 if join_wait <= 2 else 0.5
        while waited < join_wait and not is_full(chat_id):
            await asyncio.sleep(step)
            waited += step

        session = _STORE.get(chat_id)
        if not session or session["session_id"] != session_id:
            return
        chosen = choose_vampire(chat_id, logger)
        if chosen is None:
            abandon(chat_id, session_id, logger)
            await callbacks["on_abort"]()
            revealed = True
            return

        await callbacks["on_roles"](chosen)
        await asyncio.sleep(guess_wait)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        log_error(logger, f"FOX VAMPIRE LOOP FAILED chat_id={chat_id} error={error!r}")
    finally:
        if not revealed:
            session = _STORE.get(chat_id)
            if session and session["session_id"] == session_id:
                vampire = reveal(chat_id, session_id, logger)
                if vampire is not None:
                    try:
                        await callbacks["on_timeout"](vampire)
                    except Exception as error:
                        log_error(logger, f"FOX VAMPIRE REVEAL FAILED "
                                          f"chat_id={chat_id} error={error!r}")


def schedule(chat_id, session_id, callbacks, logger=None,
             join_seconds=None, guess_seconds=None):
    return _STORE.schedule(chat_id, lambda: run_game(
        chat_id, session_id, callbacks, logger, join_seconds, guess_seconds))


def reset_all(chat_id=None):
    _STORE.reset(chat_id)
