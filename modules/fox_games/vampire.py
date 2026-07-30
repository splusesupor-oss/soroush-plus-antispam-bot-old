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
CHOSEN_MESSAGE = (
    "🩸 پیام خصوصی خون‌آشام برای یکی از بازیکنان ارسال شد. "
    "حالا حدس بزنید خون‌آشام کیست!"
)
# وقتی پیام خصوصی نرسد بازی اصلاً وارد مرحلهٔ حدس نمی‌شود.
DM_FAILED_MESSAGE = (
    "❌ ارسال پیام خصوصی به خون‌آشام ناموفق بود؛ بازی لغو شد.\n\n"
    "بازیکن باید یک بار به ربات پیام خصوصی بدهد تا امکان ارسال فراهم شود."
)


async def send_role_dm(client, player, logger=None, chat_id=None):
    """پیام نقش را به پیوی خون‌آشام می‌فرستد.

    ``(ok, error)`` برمی‌گرداند. هیچ خطایی بی‌صدا نادیده گرفته نمی‌شود.

    ترتیب تلاش:
      ۱. شیء کاربر که هنگام «شرکت» ذخیره شده — دارای access_hash و بدون
         نیاز به کش یا شبکه.
      ۲. شناسهٔ عددی، فقط به عنوان آخرین راه (روی StringSession معمولاً
         بعد از ری‌استارت شکست می‌خورد).
    """
    user_id = player.get("user_id")
    targets = []
    peer = player.get("peer")
    if peer is not None:
        targets.append(("peer_object", peer))
    if user_id is not None:
        targets.append(("user_id", user_id))

    if not targets:
        log_error(logger, f"FOX VAMPIRE ROLE DM FAILED chat_id={chat_id} "
                          f"user_id={user_id} reason=no_target")
        return False, "no_target"

    last_error = None
    for label, target in targets:
        try:
            log(logger, f"FOX VAMPIRE ROLE DM TRY chat_id={chat_id} "
                        f"user_id={user_id} via={label}")
            await client.send_message(target, ROLE_MESSAGE)
            log(logger, f"FOX VAMPIRE ROLE DM SENT chat_id={chat_id} "
                        f"user_id={user_id} via={label}")
            return True, None
        except Exception as error:
            last_error = error
            log_error(logger, f"FOX VAMPIRE ROLE DM ATTEMPT FAILED "
                              f"chat_id={chat_id} user_id={user_id} "
                              f"via={label} error={error!r}")

    log_error(logger, f"FOX VAMPIRE ROLE DM FAILED chat_id={chat_id} "
                      f"user_id={user_id} error={last_error!r}")
    return False, last_error


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
        # شیء کاملِ کاربر نگه داشته می‌شود، نه فقط شناسهٔ عددی.
        #
        # ریشهٔ باگ «پیام خصوصی ارسال نمی‌شود» همین بود: با پاس دادن یک int
        # به send_message، کتابخانه اول utils.get_input_peer(int) را صدا
        # می‌زند که همیشه TypeError می‌دهد، بعد سراغ کش می‌رود. چون نشست از
        # نوع StringSession است و کشِ آن فقط در RAM زندگی می‌کند، بعد از هر
        # ری‌استارت خالی است و resolve با ValueError شکست می‌خورد. حساب هم
        # userbot است، پس مسیر ویژهٔ access_hash=0 مخصوص bot ها کار نمی‌کند.
        # شیء User خودش access_hash دارد و بدون هیچ کش یا درخواست شبکه‌ای
        # مستقیماً به InputPeerUser تبدیل می‌شود.
        "peer": user,
    }
    session["ids"].add(user_id)
    session["players"].append(player)
    log(logger, f"FOX VAMPIRE JOIN chat_id={chat_id} user_id={user_id} "
                f"name={player['name']} has_peer={user is not None} "
                f"count={len(session['players'])}")
    return "joined", list(session["players"])


def player_count(chat_id):
    session = _STORE.get(chat_id)
    return len(session["players"]) if session else 0


def is_full(chat_id):
    return player_count(chat_id) >= MAX_PLAYERS


def roster_lines(players):
    """فقط نام نمایشی بازیکنان، به ترتیب شماره.

    شماره‌ها لاتین‌اند تا دقیقاً با همان عددی که کاربر برای حدس تایپ
    می‌کند یکی باشد (``parse_int`` هر دو شکل را می‌پذیرد، ولی نمایش
    یکسان ابهام را از بین می‌برد).
    """
    return "\n".join(
        f"{index}. {player['name']}"
        for index, player in enumerate(players, 1)
    )


def choose_vampire(chat_id, logger=None):
    """یک بازیکن را تصادفی خون‌آشام می‌کند. None اگر تعداد کافی نباشد.

    مرحله عمداً روی ``assigning`` می‌ماند، نه ``guessing``. تا وقتی پیام
    خصوصی واقعاً ارسال نشده هیچ حدسی پذیرفته نمی‌شود؛ پیش از این بازی حتی
    با شکست ارسال پیوی هم باز می‌شد.
    """
    session = _STORE.get(chat_id)
    if not session or session.get("phase") != "joining":
        return None
    if len(session["players"]) < MIN_PLAYERS:
        log(logger, f"FOX VAMPIRE ABORT chat_id={chat_id} reason=not_enough_players "
                    f"count={len(session['players'])}")
        return None
    index = _RANDOM.randrange(len(session["players"]))
    session["vampire"] = index
    session["phase"] = "assigning"
    vampire = session["players"][index]
    log(logger,
        f"FOX VAMPIRE CHOSEN chat_id={chat_id} session_id={session['session_id']} "
        f"vampire_user_id={vampire['user_id']} number={index + 1} "
        f"phase=assigning")
    return {
        "number": index + 1,
        "player": dict(vampire),
        "players": list(session["players"]),
    }


def open_guessing(chat_id, session_id=None, logger=None):
    """پس از ارسال موفق پیوی، مرحلهٔ حدس را باز می‌کند."""
    session = _STORE.get(chat_id)
    if not session or session.get("phase") != "assigning":
        return False
    if session_id is not None and session["session_id"] != session_id:
        return False
    session["phase"] = "guessing"
    log(logger, f"FOX VAMPIRE GUESSING OPEN chat_id={chat_id} "
                f"session_id={session['session_id']} "
                f"seconds={GUESS_SECONDS}")
    return True


def vampire_player(chat_id):
    """بازیکن خون‌آشامِ دور فعلی، یا None."""
    session = _STORE.get(chat_id)
    if not session or session.get("vampire") is None:
        return None
    return dict(session["players"][session["vampire"]])


def guess(chat_id, user_id, text, logger=None):
    """یک حدس. خروجی ``(state, info)``.

    state در ``{"correct","wrong","not_player","already","is_vampire",
    "self_guess","bad_number","closed"}``.
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

    # کسی نمی‌تواند خودش را به عنوان خون‌آشام معرفی کند. این حدس اصلاً ثبت
    # نمی‌شود تا نوبت واقعی کاربر سوخته نشود.
    if session["players"][number - 1]["user_id"] == user_id:
        log(logger, f"FOX VAMPIRE GUESS BLOCKED chat_id={chat_id} "
                    f"user_id={user_id} reason=self_guess")
        return "self_guess", None

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
        log(logger, f"FOX VAMPIRE JOIN CLOSED chat_id={chat_id} "
                    f"session_id={session_id} players={player_count(chat_id)}")
        chosen = choose_vampire(chat_id, logger)
        if chosen is None:
            abandon(chat_id, session_id, logger)
            await callbacks["on_abort"]()
            revealed = True
            return

        # پیام خصوصی باید *قبل* از باز شدن مرحلهٔ حدس ارسال شود. اگر نرسد،
        # بازی لغو می‌شود و هیچ خطایی بی‌صدا رد نمی‌شود.
        sent = await callbacks["on_roles"](chosen)
        if sent is False:
            log_error(logger, f"FOX VAMPIRE ABORT chat_id={chat_id} "
                              f"session_id={session_id} reason=role_dm_failed")
            abandon(chat_id, session_id, logger)
            if "on_dm_failed" in callbacks:
                await callbacks["on_dm_failed"]()
            revealed = True
            return

        if not open_guessing(chat_id, session_id, logger):
            log_error(logger, f"FOX VAMPIRE ABORT chat_id={chat_id} "
                              f"session_id={session_id} reason=open_guessing_failed")
            return
        if "on_roster" in callbacks:
            await callbacks["on_roster"](chosen)
        await asyncio.sleep(guess_wait)
        log(logger, f"FOX VAMPIRE GUESS WINDOW ENDED chat_id={chat_id} "
                    f"session_id={session_id}")
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
