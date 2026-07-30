"""چهار بازی جدید Fox AI: استقلال، Race Condition، Timeout و جوایز.

    python tests/test_fox_games.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import handlers.fox_games_router as router
from modules.fox_games import laugh_or_lose as ll
from modules.fox_games import lucky_box as lb
from modules.fox_games import survival as sv
from modules.fox_games import vampire as vp
from modules.fox_games.survival_questions import LEVELS, all_questions

PASSED = FAILED = 0
CHAT = -100900


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class User:
    def __init__(self, uid, name=None, username=None):
        self.id = uid
        self.first_name = name
        self.last_name = None
        self.username = username


class Event:
    def __init__(self):
        self.out = []

    async def reply(self, text, **kwargs):
        self.out.append(text)
        return None

    def said(self, needle):
        return any(needle in message for message in self.out)


class Client:
    def __init__(self):
        self.dm = []

    async def send_message(self, target, text, **kwargs):
        self.dm.append((target, text))


class Logger:
    def __init__(self):
        self.info = []
        self.errors = []

    def log_info(self, m):
        self.info.append(m)

    def log_error(self, m):
        self.errors.append(m)

    def has(self, needle):
        return any(needle in m for m in self.info + self.errors)


class Bot:
    def __init__(self):
        self.client = Client()
        self.logger = Logger()
        self.paid = []

    def award_coins(self, chat_id, user_id, name, amount):
        self.paid.append((user_id, amount))


async def send(bot, event, uid, text, name=None, username=None):
    return await router.handle(
        bot, event, CHAT, uid, User(uid, name, username), text, bot.logger
    )


async def noop(*args, **kwargs):
    pass


# ==========================================================================
# 😂 بخند یا بباز
# ==========================================================================
def test_laugh():
    print("\n### 😂 بخند یا بباز")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "بخند یا بباز")
        started = ll.is_active(CHAT)

        again = Event()
        await send(bot, again, 2, "بخند یا بباز")
        blocked = again.said("همین حالا در جریان")

        session_id = ll._STORE.get(CHAT)["session_id"]
        early = await send(bot, event, 5, "😂", "Early")
        ll.open_round(CHAT, session_id)

        first = await send(bot, event, 10, "😂 خیلی خنده‌دار بود", "Ali")
        second = await send(bot, event, 11, "🤣", "Reza")
        return bot, event, started, blocked, early, first, second

    bot, event, started, blocked, early, first, second = asyncio.run(scenario())
    check("بازی شروع شد", started)
    check("اجرای دوباره مسدود شد", blocked)
    check("خنده پیش از پایان شمارش پذیرفته نمی‌شود", not early)
    check("اولین خنده برنده است", first)
    check("نفر دوم نادیده گرفته می‌شود", not second)
    check("برنده ۱ سکه گرفت", bot.paid == [(10, 1)], f"-> {bot.paid}")
    check("بازی بلافاصله بسته شد", not ll.is_active(CHAT))
    check("نام برنده اعلام شد", event.said("برنده"))


def test_laugh_emoji_set():
    print("\n### 😂 ایموجی‌های مجاز")
    for emoji in ("😂", "🤣", "😆", "😹", "😄", "😁"):
        check(f"{emoji} پذیرفته می‌شود", ll.contains_laugh(emoji))
    for emoji in ("😀", "🙂", "❤️", "سلام"):
        check(f"{emoji} پذیرفته نمی‌شود", not ll.contains_laugh(emoji))


def test_laugh_timeout():
    print("\n### 😂 پایان بدون برنده")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        session = ll.start(CHAT, bot.logger)
        fired = []

        async def on_timeout():
            fired.append(True)

        ll.schedule(CHAT, session["session_id"], noop, noop, on_timeout,
                    logger=bot.logger, countdown=0, timeout=0.1)
        await asyncio.sleep(0.4)
        return fired

    fired = asyncio.run(scenario())
    check("پیام پایان ارسال شد", fired == [True])
    check("session آزاد شد", not ll.is_active(CHAT))


# ==========================================================================
# 🏕 بقا
# ==========================================================================
def test_survival_registration():
    print("\n### 🏕 ثبت‌نام بقا")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "بقا")
        again = Event()
        await send(bot, again, 2, "بقا")
        blocked = again.said("همین حالا در جریان")
        # تایمر واقعی ثبت‌نام را می‌بندد؛ برای این تست آن را متوقف می‌کنیم تا
        # فقط منطق ثبت‌نام سنجیده شود.
        sv._STORE.cancel_task(CHAT)
        for uid in (21, 22, 23, 24):
            await send(bot, event, uid, "شرکت", f"P{uid}")
        dup = Event()
        await router.handle(bot, dup, CHAT, 21, User(21, "P21"), "شرکت", bot.logger)
        overflow = Event()
        await router.handle(bot, overflow, CHAT, 25, User(25, "P25"),
                            "شرکت", bot.logger)
        return blocked, dup, overflow

    blocked, dup, overflow = asyncio.run(scenario())
    check("اجرای دوباره مسدود شد", blocked)
    check("۴ نفر ثبت شدند", sv.player_count(CHAT) == 4, f"-> {sv.player_count(CHAT)}")
    check("ظرفیت تکمیل است", sv.is_full(CHAT))
    check("ثبت‌نام تکراری رد شد", dup.said("قبلاً ثبت‌نام"))
    check("نفر پنجم رد شد", overflow.said("ظرفیت تکمیل"))
    router.reset_all()


def test_survival_full_game():
    print("\n### 🏕 بازی کامل بقا")

    async def scenario():
        router.reset_all()
        bot = Bot()
        sv.start(CHAT, bot.logger)
        sid = sv._STORE.get(CHAT)["session_id"]
        for uid in (1, 2, 3, 4):
            sv.join(CHAT, uid, User(uid, f"P{uid}"), bot.logger)
        finished = []

        async def on_finish(champion):
            finished.append(champion)

        sv.schedule(CHAT, sid, {
            "on_abort": noop, "on_begin": noop, "on_question": noop,
            "on_eliminated": noop, "on_finish": on_finish,
        }, logger=bot.logger, join_seconds=0.05, answer_seconds=0.2)

        for _ in range(20):
            await asyncio.sleep(0.12)
            session = sv._STORE.get(CHAT)
            if not session or not session.get("question"):
                break
            alive = [p for p in session["players"].values() if p["alive"]]
            if len(alive) <= 1:
                break
            sv.answer(CHAT, alive[0]["user_id"], session["question"]["answer"])
            await asyncio.sleep(0.22)
        await asyncio.sleep(0.8)
        return bot, finished

    bot, finished = asyncio.run(scenario())
    check("بازی پایان یافت", len(finished) == 1, f"-> {len(finished)}")
    check("برنده مشخص شد", finished and finished[0] is not None,
          f"-> {finished}")
    check("session بسته شد", not sv.is_active(CHAT))
    check("حذف بازیکن لاگ شد", bot.logger.has("FOX SURVIVAL ELIMINATED"))
    router.reset_all()


def test_survival_wrong_answer_eliminates():
    print("\n### 🏕 پاسخ اشتباه = حذف")
    router.reset_all()
    logger = Logger()
    sv.start(CHAT, logger)
    for uid in (1, 2, 3, 4):
        sv.join(CHAT, uid, User(uid, f"P{uid}"), logger)
    sv.begin_rounds(CHAT, logger)
    sv.next_question(CHAT, logger)
    session = sv._STORE.get(CHAT)
    correct = session["question"]["answer"]

    state, _ = sv.answer(CHAT, 1, correct)
    check("پاسخ درست پذیرفته شد", state == "correct")
    state, _ = sv.answer(CHAT, 2, "پاسخ کاملا اشتباه")
    check("پاسخ اشتباه حذف می‌کند", state == "wrong")
    state, _ = sv.answer(CHAT, 1, correct)
    check("پاسخ دوم همان کاربر رد می‌شود", state == "already")
    state, _ = sv.answer(CHAT, 99, correct)
    check("غیر بازیکن پذیرفته نمی‌شود", state == "not_player")
    removed = sv.eliminate_silent(CHAT, logger)
    check("ساکت‌ها حذف شدند", len(removed) == 2, f"-> {len(removed)}")
    check("فقط یک بازمانده", len(sv.alive_players(CHAT)) == 1)
    router.reset_all()


def test_survival_questions():
    print("\n### 🏕 بانک سوال")
    questions = all_questions()
    check(f"بانک بزرگ است ({len(questions)} سوال)", len(questions) >= 50)
    texts = [q[0] for q in questions]
    check("هیچ سوال تکراری نیست", len(texts) == len(set(texts)))
    check("چند سطح سختی دارد", len(LEVELS) >= 4, f"-> {len(LEVELS)}")
    check("همهٔ سوال‌ها پاسخ دارند", all(q[1] for q in questions))

    router.reset_all()
    logger = Logger()
    sv.start(CHAT, logger)
    for uid in (1, 2):
        sv.join(CHAT, uid, User(uid, f"P{uid}"), logger)
    sv.begin_rounds(CHAT, logger)
    seen = []
    for _ in range(8):
        question = sv.next_question(CHAT, logger)
        if question is None:
            break
        seen.append(question["text"])
    check("سوال‌ها در یک بازی تکرار نمی‌شوند",
          len(seen) == len(set(seen)), f"-> {len(seen)} vs {len(set(seen))}")
    check("سطح هر مرحله بالا می‌رود",
          sv._STORE.get(CHAT)["level"] == len(seen))
    router.reset_all()


# ==========================================================================
# 🎁 جعبه شانسی
# ==========================================================================
def test_lucky_box_layout():
    print("\n### 🎁 چیدمان جعبه‌ها")
    for _ in range(30):
        boxes = lb.build_boxes()
        empties = sum(1 for value in boxes.values() if value == 0)
        prizes = [v for v in boxes.values() if v > 0]
        if len(boxes) != 9 or empties != 4 or len(prizes) != 5:
            check("چیدمان درست است", False, f"-> {boxes}")
            return
        if not all(1 <= p <= 15 for p in prizes):
            check("جوایز بین ۱ تا ۱۵", False, f"-> {prizes}")
            return
    check("همیشه ۹ جعبه", True)
    check("همیشه ۴ پوچ و ۵ جایزه", True)
    check("جوایز بین ۱ تا ۱۵ سکه", True)
    layouts = {tuple(sorted(lb.build_boxes().items())) for _ in range(20)}
    check("هیچ الگوی ثابتی نیست", len(layouts) > 1, f"-> {len(layouts)}")


def test_lucky_box_play_and_quota():
    print("\n### 🎁 بازی و سهمیهٔ روزانه")

    async def scenario():
        router.reset_all()
        lb.reset_all(clear_quota=True)
        bot = Bot()
        user = 30

        first = Event()
        await send(bot, first, user, "جعبه شانسی")
        board = first.said("┌───┬───┬───┐")
        other = await send(bot, first, 99, "5")
        await send(bot, first, user, "5")
        opened = first.said("باز شد")

        second = Event()
        await send(bot, second, user, "جعبه شانسی")
        await send(bot, second, user, "3")

        third = Event()
        await send(bot, third, user, "جعبه شانسی")
        return bot, board, other, opened, third

    bot, board, other, opened, third = asyncio.run(scenario())
    check("جدول نمایش داده شد", board)
    check("فقط صاحب بازی می‌تواند انتخاب کند", not other)
    check("جعبه باز شد", opened)
    check("بار سوم مسدود شد", third.said("سهمیه امروز شما تمام شده است"))
    check("زمان باقی‌مانده واقعی نمایش داده شد", third.said("دیگر"))
    check("سهمیه صفر شد", lb.remaining_plays(30) == 0)
    check("زمان انتظار مثبت است", lb.seconds_until_next(30) > 0)
    lb.reset_all(clear_quota=True)


def test_lucky_box_wait_format():
    print("\n### 🎁 قالب زمان انتظار")
    check("ساعت و دقیقه", "ساعت" in lb.format_wait(8 * 3600 + 23 * 60)
          and "دقیقه" in lb.format_wait(8 * 3600 + 23 * 60))
    check("فقط دقیقه", lb.format_wait(600).endswith("دقیقه دیگر"))
    check("کمتر از یک دقیقه", "کمتر از یک دقیقه" in lb.format_wait(30))


# ==========================================================================
# 🧛 خون‌آشام
# ==========================================================================
def test_vampire_full_game():
    print("\n### 🧛 بازی کامل خون‌آشام")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "خون آشام")
        again = Event()
        await send(bot, again, 2, "خون آشام")
        blocked = again.said("همین حالا در جریان")

        names = {41: "علی", 42: "حسین", 43: "محمد", 44: "میلاد"}
        for uid, name in names.items():
            await send(bot, event, uid, "شرکت", name)
        session_id = vp._STORE.get(CHAT)["session_id"]

        async def on_roles(chosen):
            await event.reply(
                "🧛 شرکت‌کنندگان:\n\n"
                + vp.roster_lines(chosen["players"])
                + f"\n\n{vp.CHOSEN_MESSAGE}"
            )
            await bot.client.send_message(chosen["player"]["user_id"],
                                          vp.ROLE_MESSAGE)

        vp.schedule(CHAT, session_id, {
            "on_abort": noop, "on_roles": on_roles, "on_timeout": noop,
        }, logger=bot.logger, join_seconds=0.05, guess_seconds=5)
        await asyncio.sleep(0.3)

        session = vp._STORE.get(CHAT)
        index = session["vampire"]
        vampire_uid = session["players"][index]["user_id"]
        number = index + 1

        self_state, _ = vp.guess(CHAT, vampire_uid, str(number), bot.logger)
        self_guess = self_state == "is_vampire"
        others = [p["user_id"] for p in session["players"]
                  if p["user_id"] != vampire_uid]
        wrong_number = 1 if number != 1 else 2
        await send(bot, event, others[0], str(wrong_number))
        second_guess = await send(bot, event, others[0], str(number))
        await send(bot, event, others[1], str(number))
        return bot, event, blocked, self_guess, second_guess, vampire_uid, others

    (bot, event, blocked, self_guess, second_guess,
     vampire_uid, others) = asyncio.run(scenario())
    check("اجرای دوباره مسدود شد", blocked)
    check("فقط خون‌آشام پیام خصوصی گرفت",
          len(bot.client.dm) == 1 and bot.client.dm[0][0] == vampire_uid,
          f"-> {bot.client.dm}")
    check("متن نقش درست است", bot.client.dm[0][1] == vp.ROLE_MESSAGE)
    check("فهرست شماره‌دار نمایش داده شد", event.said("۱."))
    check("اعلام انتخاب خون‌آشام", event.said(vp.CHOSEN_MESSAGE))
    check("خون‌آشام نمی‌تواند حدس بزند", self_guess)
    check("حدس دوم همان نفر نادیده گرفته شد", second_guess)
    check("حدس درست بازی را تمام کرد", not vp.is_active(CHAT))
    check("برنده ۷ سکه گرفت", bot.paid == [(others[1], vp.WINNER_COINS)],
          f"-> {bot.paid}")
    check("نام خون‌آشام اعلام شد", event.said("🧛 خون‌آشام:"))
    router.reset_all()


def test_vampire_timeout_reveals():
    print("\n### 🧛 پایان زمان و افشای خون‌آشام")

    async def scenario():
        router.reset_all()
        bot = Bot()
        vp.start(CHAT, bot.logger)
        session_id = vp._STORE.get(CHAT)["session_id"]
        for uid, name in ((51, "علی"), (52, "حسین"), (53, "محمد"), (54, "رضا")):
            vp.join(CHAT, uid, User(uid, name, f"u{uid}"), bot.logger)
        revealed = []

        async def on_timeout(vampire):
            revealed.append(vampire)

        vp.schedule(CHAT, session_id, {
            "on_abort": noop, "on_roles": noop, "on_timeout": on_timeout,
        }, logger=bot.logger, join_seconds=0.05, guess_seconds=0.15)
        await asyncio.sleep(0.6)
        return revealed

    revealed = asyncio.run(scenario())
    check("خون‌آشام افشا شد", len(revealed) == 1, f"-> {len(revealed)}")
    check("session بسته شد", not vp.is_active(CHAT))
    if revealed:
        text = vp.format_reveal(revealed[0])
        check("متن پایان درست است", "⏰ زمان تمام شد." in text
              and "🧛 خون‌آشام:" in text)
        check("یوزرنیم نمایش داده شد", "(@u" in text, f"-> {text}")
    router.reset_all()


def test_vampire_minimum_players():
    print("\n### 🧛 حداقل بازیکن")

    async def scenario():
        router.reset_all()
        bot = Bot()
        vp.start(CHAT, bot.logger)
        session_id = vp._STORE.get(CHAT)["session_id"]
        for uid in (61, 62):
            vp.join(CHAT, uid, User(uid, f"P{uid}"), bot.logger)
        aborted = []

        async def on_abort():
            aborted.append(True)

        vp.schedule(CHAT, session_id, {
            "on_abort": on_abort, "on_roles": noop, "on_timeout": noop,
        }, logger=bot.logger, join_seconds=0.05, guess_seconds=0.1)
        await asyncio.sleep(0.4)
        return aborted

    aborted = asyncio.run(scenario())
    check("با کمتر از ۴ نفر لغو شد", aborted == [True])
    check("session آزاد شد", not vp.is_active(CHAT))
    router.reset_all()


def test_vampire_display_names():
    print("\n### 🧛 نام نمایشی")
    from modules.fox_games.session_core import display_name
    check("Display Name اولویت دارد",
          display_name(User(1, "علی", "ali_x")) == "علی")
    check("در نبود نام، یوزرنیم", display_name(User(2, None, "ali_x")) == "@ali_x")
    check("در نبود هر دو، جایگزین مناسب",
          display_name(User(3, None, None)) == "بازیکن 3")


# ==========================================================================
# استقلال و همزیستی
# ==========================================================================
def test_isolation_between_fox_games():
    print("\n### استقلال چهار بازی از هم")

    async def scenario():
        router.reset_all()
        lb.reset_all(clear_quota=True)
        bot, event = Bot(), Event()
        await send(bot, event, 1, "بخند یا بباز")
        await send(bot, event, 2, "بقا")
        await send(bot, event, 3, "خون آشام")
        await send(bot, event, 4, "جعبه شانسی")
        return (ll.is_active(CHAT), sv.is_active(CHAT),
                vp.is_active(CHAT), lb.is_active(CHAT))

    laugh, survive, vamp, box = asyncio.run(scenario())
    check("هر چهار بازی هم‌زمان مستقل فعال‌اند",
          laugh and survive and vamp and box,
          f"-> {laugh} {survive} {vamp} {box}")

    stores = [id(ll._STORE), id(sv._STORE), id(lb._STORE), id(vp._STORE)]
    check("هر بازی SessionStore جدا دارد", len(set(stores)) == 4)
    router.reset_all()
    lb.reset_all(clear_quota=True)


def test_isolation_from_legacy_games():
    print("\n### استقلال از بازی‌های قدیمی")
    import modules.flag_guess as fg
    import modules.name_family as nf
    import modules.riddles as rd

    async def scenario():
        router.reset_all()
        fg.reset_history()
        nf.reset_all()
        rd.used_riddles.clear()
        bot, event = Bot(), Event()

        nf.start(CHAT)
        fg.start(CHAT, 1)
        rd.new_riddle(CHAT, 1)
        await send(bot, event, 1, "بخند یا بباز")
        await send(bot, event, 2, "بقا")

        legacy_ok = nf.is_active(CHAT) and fg.is_active(CHAT)
        fox_ok = ll.is_active(CHAT) and sv.is_active(CHAT)
        return legacy_ok, fox_ok

    legacy_ok, fox_ok = asyncio.run(scenario())
    check("بازی‌های قدیمی دست‌نخورده ماندند", legacy_ok)
    check("بازی‌های جدید هم‌زمان فعال شدند", fox_ok)

    fox_state = {id(ll._STORE._sessions), id(sv._STORE._sessions),
                 id(lb._STORE._sessions), id(vp._STORE._sessions)}
    legacy_state = {id(nf._ACTIVE), id(fg._ACTIVE), id(rd.active_riddles)}
    check("هیچ ساختار داده‌ای مشترک نیست", not (fox_state & legacy_state))
    router.reset_all()
    nf.reset_all()
    fg.reset_history()


def test_router_ignores_unrelated_text():
    print("\n### روتر پیام‌های نامرتبط را مصرف نمی‌کند")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        results = []
        for text in ("سلام", "اسم فامیل", "حدس پرچم", "چیستان", "راهنما"):
            results.append(await send(bot, event, 1, text))
        return results

    results = asyncio.run(scenario())
    check("هیچ پیام نامرتبطی مصرف نشد", not any(results), f"-> {results}")


def test_sequential_sessions():
    print("\n### چند session پشت سر هم")

    async def scenario():
        router.reset_all()
        bot = Bot()
        wins = 0
        for index in range(4):
            event = Event()
            await send(bot, event, 1, "بخند یا بباز")
            session = ll._STORE.get(CHAT)
            if session is None:
                break
            ll.open_round(CHAT, session["session_id"])
            if await send(bot, event, 10 + index, "😂", f"P{index}"):
                wins += 1
        return wins, bot

    wins, bot = asyncio.run(scenario())
    check("هر ۴ بازی پشت سر هم کار کرد", wins == 4, f"-> {wins}")
    check("۴ جایزه پرداخت شد", len(bot.paid) == 4, f"-> {bot.paid}")
    router.reset_all()


def test_real_coin_payout():
    """جایزه باید روی موجودی واقعی بنشیند، حتی وقتی bot متد award_coins ندارد.

    گارد رگرسیون: قبلاً روتر به ``getattr(bot, "award_coins")`` تکیه می‌کرد و
    چون شیء واقعی ربات چنین متدی ندارد، هیچ سکه‌ای پرداخت نمی‌شد.
    """
    print("\n### پرداخت واقعی سکه (بدون award_coins روی bot)")
    import tempfile
    import pathlib
    import modules.coins as coins

    original_file = coins.FILE
    coins.FILE = pathlib.Path(tempfile.mkdtemp()) / "coins.json"
    coins._cache = None
    coins._cache_mtime = None

    class RealBot:
        """مثل شیء واقعی ربات: هیچ متد award_coins ندارد."""

        def __init__(self):
            self.client = Client()
            self.logger = Logger()

    try:
        check("شیء ربات واقعی متد award_coins ندارد",
              not hasattr(RealBot(), "award_coins"))

        async def scenario():
            router.reset_all()
            bot, event = RealBot(), Event()
            await send(bot, event, 1, "بخند یا بباز")
            ll.open_round(CHAT, ll._STORE.get(CHAT)["session_id"], bot.logger)
            await send(bot, event, 10, "😂", "Ali")

            vp.start(CHAT, bot.logger)
            for uid, name in ((41, "a"), (42, "b"), (43, "c"), (44, "d")):
                vp.join(CHAT, uid, User(uid, name), bot.logger)
            chosen = vp.choose_vampire(CHAT, bot.logger)
            guesser = next(p["user_id"] for p in chosen["players"]
                           if p["user_id"] != chosen["player"]["user_id"])
            await send(bot, event, guesser, str(chosen["number"]))
            return bot, guesser

        bot, guesser = asyncio.run(scenario())
        check("برندهٔ بخند یا بباز ۱ سکه گرفت",
              coins.get_profile(CHAT, 10)["coins"] == 1,
              f"-> {coins.get_profile(CHAT, 10)['coins']}")
        check("برندهٔ خون‌آشام ۷ سکه گرفت",
              coins.get_profile(CHAT, guesser)["coins"] == 7,
              f"-> {coins.get_profile(CHAT, guesser)['coins']}")
        check("پرداخت لاگ شد", bot.logger.has("FOX REWARD PAID"))

        # بقا
        router.reset_all()
        logger = Logger()
        sv.start(CHAT, logger)
        for uid in (61, 62, 63, 64):
            sv.join(CHAT, uid, User(uid, f"P{uid}"), logger)
        sv._STORE.cancel_task(CHAT)
        sv.begin_rounds(CHAT, logger)
        sv.next_question(CHAT, logger)
        session = sv._STORE.get(CHAT)
        sv.answer(CHAT, 61, session["question"]["answer"], logger)
        sv.eliminate_silent(CHAT, logger)
        champion = sv.finish(CHAT, None, logger)
        router._coins(RealBot(), CHAT, champion["user_id"],
                      champion["name"], sv.WINNER_COINS, logger)
        check("برندهٔ بقا ۸ سکه گرفت",
              coins.get_profile(CHAT, champion["user_id"])["coins"] == 8,
              f"-> {coins.get_profile(CHAT, champion['user_id'])['coins']}")
    finally:
        coins.FILE = original_file
        coins._cache = None
        coins._cache_mtime = None
        router.reset_all()


def test_reward_values():
    print("\n### مقادیر جایزه مطابق راهنما")
    check("بخند یا بباز = ۱ سکه", ll.WINNER_COINS == 1, f"-> {ll.WINNER_COINS}")
    check("بقا = ۸ سکه", sv.WINNER_COINS == 8, f"-> {sv.WINNER_COINS}")
    check("خون‌آشام = ۷ سکه", vp.WINNER_COINS == 7, f"-> {vp.WINNER_COINS}")
    check("زمان حدس خون‌آشام = ۵۰ ثانیه", vp.GUESS_SECONDS == 50,
          f"-> {vp.GUESS_SECONDS}")


def test_logging():
    print("\n### لاگ کامل")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "بخند یا بباز")
        ll.open_round(CHAT, ll._STORE.get(CHAT)["session_id"], bot.logger)
        await send(bot, event, 10, "😂", "Ali")
        await send(bot, event, 1, "بقا")
        await send(bot, event, 21, "شرکت", "P21")
        return bot

    bot = asyncio.run(scenario())
    for needle in ("FOX LAUGH START", "FOX LAUGH OPEN", "FOX LAUGH WINNER",
                   "FOX SURVIVAL START", "FOX SURVIVAL JOIN"):
        check(f"لاگ موجود: {needle}", bot.logger.has(needle))
    router.reset_all()


def main():
    test_laugh()
    test_laugh_emoji_set()
    test_laugh_timeout()
    test_survival_registration()
    test_survival_full_game()
    test_survival_wrong_answer_eliminates()
    test_survival_questions()
    test_lucky_box_layout()
    test_lucky_box_play_and_quota()
    test_lucky_box_wait_format()
    test_vampire_full_game()
    test_vampire_timeout_reveals()
    test_vampire_minimum_players()
    test_vampire_display_names()
    test_isolation_between_fox_games()
    test_isolation_from_legacy_games()
    test_router_ignores_unrelated_text()
    test_sequential_sessions()
    test_real_coin_payout()
    test_reward_values()
    test_logging()

    print(f"\n{'=' * 52}")
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
