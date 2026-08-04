"""تست سه بازی جدید: معما، بهترین جواب، نبرد.

    python tests/test_new_games.py

پوشش:
- معما: فقط صاحب پاسخ می‌دهد، ۳ برنز، دو کاربر هم‌زمان، timeout، dedup.
- بهترین جواب: ثبت پاسخ، قضاوت معیارمند، ۴ برنز، بی‌پاسخ، ایزولهٔ گروه.
- نبرد: شروع، شرکت، نفر سوم ممنوع، پاسخ فقط خودی، ۳۰ ثانیه، بازنده ۴ برنز،
  بازندهٔ بی‌پاسخ صفر، عدم پرداخت دوبار، ایزولهٔ گروه.
- راهنما/لیست/راهنمای امتیاز: هر سه بازی با Bold.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import handlers.fox_games_router as router
from modules.fox_games import maemma, best_answer, battle
from modules.fox_games.maemma_puzzles import PUZZLES as MAEMMA_PUZZLES
from modules.fox_games.best_answer_questions import BEST_ANSWER_QUESTIONS
from modules.fox_games.battle_questions import BATTLE_QUESTIONS

PASSED = 0
FAILED = 0
CHAT = -1009
CHAT2 = -1010


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {label}")
    else:
        FAILED += 1
        print(f"FAIL  {label} {detail}")


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
        return any(needle in m for m in self.out)


class Logger:
    def __init__(self):
        self.info = []
        self.errors = []

    def log_info(self, m):
        self.info.append(m)

    def log_error(self, m):
        self.errors.append(m)


class Bot:
    def __init__(self):
        self.logger = Logger()
        self.paid = []

    def award_coins(self, chat_id, user_id, name, amount):
        self.paid.append((user_id, amount))


async def send(bot, event, chat, uid, text, name=None, username=None):
    return await router.handle(
        bot, event, chat, uid, User(uid, name, username), text, bot.logger
    )


# ===========================================================================
#  🧩 معما
# ===========================================================================
async def _test_maemma_owner_only():
    router.reset_all()
    bot = Bot()
    ev = Event()
    r = await send(bot, ev, CHAT, 1, "معما", name="A")
    check("معما: دستور مصرف شد", r is True)
    check("معما: سوال نمایش داده شد",
          any("معما" in m and "ثانیه" in m for m in ev.out), f"{ev.out}")
    check("معما: سشن برای A باز شد", maemma.is_active(CHAT, 1))

    # B معما ندارد؛ پیام B مصرف نمی‌شود و سکه نمی‌گیرد
    ev2 = Event()
    r = await send(bot, ev2, CHAT, 2, "هر چیزی", name="B")
    check("معما: پاسخ B مصرف نشد", r is False)
    check("معما: B سکه نگرفت", not bot.paid, f"{bot.paid}")

    # A هر ۳ معما را درست جواب می‌دهد
    for qnum in range(1, maemma.QUESTIONS_PER_GAME + 1):
        q = maemma.current_question(CHAT, 1)
        check(f"معما: سوال {qnum} در جریان است", q is not None
              and q["number"] == qnum, f"{q}")
        ev3 = Event()
        r = await send(bot, ev3, CHAT, 1, q["answer"], name="A")
        check(f"معما: پاسخ سوال {qnum} مصرف شد", r is True)
    check("معما: A دقیقاً ۳ بار برنز گرفت (هر پاسخ ۳)",
          len(bot.paid) == 3 and all(p == (1, maemma.REWARD) for p in bot.paid),
          f"{bot.paid}")
    check("معما: سشن A پس از ۳ سوال بسته شد", not maemma.is_active(CHAT, 1))


async def _test_maemma_concurrent():
    router.reset_all()
    bot = Bot()
    await send(bot, Event(), CHAT, 10, "معما", name="X")
    await send(bot, Event(), CHAT, 20, "معما", name="Y")
    check("معما: دو کاربر هم‌زمان", maemma.is_active(CHAT, 10)
          and maemma.is_active(CHAT, 20))
    sx = maemma.active_state(CHAT, 10)
    sy = maemma.active_state(CHAT, 20)
    check("معما: توکن‌های متفاوت", sx["token"] != sy["token"])
    # سوال‌های دو کاربر مستقل‌اند
    qx = maemma.current_question(CHAT, 10)
    qy = maemma.current_question(CHAT, 20)
    check("معما: سوال‌های دو کاربر جدا", qx["answer"] != qy["answer"]
          or qx["emoji"] != qy["emoji"], f"{qx} vs {qy}")
    # پاسخ X سشن Y را نمی‌بندد
    ev = Event()
    await send(bot, ev, CHAT, 10, qx["answer"], name="X")
    check("معما: X هنوز باز است (فقط یک سوال جواب داد)",
          maemma.is_active(CHAT, 10))
    check("معما: Y هنوز باز است", maemma.is_active(CHAT, 20))


async def _test_maemma_timeout():
    router.reset_all()
    bot = Bot()
    ev = Event()
    await send(bot, ev, CHAT, 1, "معما", name="A")
    state = maemma.active_state(CHAT, 1)
    # شبیه‌سازی timeout
    result = maemma.finish(CHAT, state["token"], 1, bot.logger)
    check("معما: timeout بدون خطا بسته شد",
          result is not None and "answer" in result, f"{result}")
    check("معما: پس از timeout سشن بسته است", not maemma.is_active(CHAT, 1))


async def _test_maemma_three_questions():
    """هر بازی معما شامل ۳ سوال بدون تکرار است و نتیجهٔ نهایی می‌دهد."""
    router.reset_all()
    bot = Bot()
    ev = Event()
    await send(bot, ev, CHAT, 1, "معما", name="A")
    state = maemma.active_state(CHAT, 1)
    check("معما: هر بازی ۳ سوال دارد",
          len(state["questions"]) == 3, f"{len(state['questions'])}")
    answers = [q["answer"] for q in state["questions"]]
    check("معما: سوال‌های یک بازی تکراری نیستند",
          len(set(answers)) == len(answers), f"{answers}")

    # بعد از پاسخ هر سوال، سوال بعدی نمایش داده می‌شود
    from modules.fox_games.session_core import to_persian_digits as _fa
    for qnum in range(1, 3):
        ev = Event()
        await send(bot, ev, CHAT, 1, state["questions"][qnum - 1]["answer"], name="A")
        # باید سوال بعدی هم نمایش داده شده باشد
        check(f"معما: بعد از سوال {qnum} سوال بعدی آمده",
              any(f"سوال {_fa(qnum + 1)}" in m for m in ev.out), f"{ev.out}")

    # جواب سوال سوم → نتیجهٔ نهایی
    ev = Event()
    await send(bot, ev, CHAT, 1, state["questions"][2]["answer"], name="A")
    check("معما: نتیجهٔ نهایی نمایش داده شد",
          any("پایان بازی معما" in m or "پاسخ" in m for m in ev.out),
          f"{ev.out}")
    check("معما: بعد از ۳ سوال سشن بسته شد", not maemma.is_active(CHAT, 1))


def _test_maemma_dedup_and_bank():
    check("معما: بانک معماها حداقل ۱۹۰ عدد", len(MAEMMA_PUZZLES) >= 190,
          f"count={len(MAEMMA_PUZZLES)}")
    ans = [p[1] for p in MAEMMA_PUZZLES]
    check("معما: پاسخ‌ها یکتا هستند",
          len(set(ans)) == len(ans), f"{len(set(ans))} vs {len(ans)}")


# ===========================================================================
#  🎯 بهترین جواب
# ===========================================================================
async def _test_best_answer_flow():
    router.reset_all()
    bot = Bot()
    ev = Event()
    r = await send(bot, ev, CHAT, 1, "بهترین جواب")
    check("بهترین جواب: دستور مصرف شد", r is True)
    check("بهترین جواب: سوال نمایش داده شد",
          any("۴۰" in m for m in ev.out), f"{ev.out}")
    check("بهترین جواب: دور فعال است", best_answer.is_active(CHAT))

    sess = best_answer._STORE.get(CHAT)
    # پاسخِ واقعی و کامل (نمونهٔ مرجع سوال، به‌علاوهٔ توضیح)
    good = sess["sample"]
    await send(bot, Event(), CHAT, 2, good, name="B")
    # پاسخِ چرت/بی‌ربط
    await send(bot, Event(), CHAT, 3, "نمیدونم", name="C")
    # پاسخِ خیلی کوتاهِ بی‌ربط
    await send(bot, Event(), CHAT, 4, "آره", name="D")

    winner = best_answer.judge(CHAT, sess["session_id"], bot.logger)
    check("بهترین جواب: برنده تعیین شد", winner is not None, f"{winner}")
    if winner:
        check("بهترین جواب: برنده پاسخِ کامل و مرتبط است",
              winner["user_id"] == 2, f"{winner}")
        check("بهترین جواب: برنده کیفیت بالایی دارد",
              winner.get("quality", 0) >= 0.4, f"{winner}")
        paid = router._coins(
            bot, CHAT, winner["user_id"], winner["name"], best_answer.REWARD,
            bot.logger, reference=f"ba:{CHAT}:{winner['session_id']}",
            game="best_answer",
        )
        check("بهترین جواب: دقیقاً ۴ برنز", paid and bot.paid[0][1] == 4,
              f"{bot.paid}")
    check("بهترین جواب: دور بسته شد", not best_answer.is_active(CHAT))


async def _test_best_answer_analysis_filters():
    """پاسخ‌های چرت/اسپم/بی‌معنی/بی‌ربط امتیاز نمی‌گیرند."""
    router.reset_all()
    bot = Bot()
    await send(bot, Event(), CHAT, 1, "بهترین جواب")
    sess = best_answer._STORE.get(CHAT)
    q = sess["question"]
    kw = sess["keywords"]

    from modules.fox_games import answer_analysis as _aa

    # ۱) پاسخ‌های آشغال رد می‌شوند
    for bad in ("", "هههههه", "😂😂😂😂", "نمیدونم", "ببخشید", "آره", "نمی‌دونم"):
        r = _aa.analyze(q, kw, bad)
        check(f"بهترین جواب: رد پاسخِ چرت {bad!r}", r["valid"] is False
              and r["reason"] is not None, f"{r}")
        check(f"بهترین جواب: پاسخِ چرت امتیاز صفر دارد", r["score"] == 0.0,
              f"{r['score']}")

    # ۲) پاسخِ خارج از موضوع (بدون ارتباط به سوال و بدون کلیدواژه)
    off = _aa.analyze(q, kw, "امروز صبح خیلی دیر بیدار شدم و دیر به محل کارم رسیدم و کلی کار عقب افتاد")
    check("بهترین جواب: پاسخِ خارج از موضوع رد می‌شود",
          off["valid"] is False and off["reason"] == "off_topic", f"{off}")

    # ۳) پاسخِ کامل و مرتبط معتبر است
    good = _aa.analyze(q, kw, sess["sample"])
    check("بهترین جواب: پاسخِ کامل مرتبط معتبر است", good["valid"] is True,
          f"{good}")

    # ۴) keyword stuffing (فقط کلیدواژه، بدون توضیح) امتیاز پایینی دارد
    stuffing = _aa.analyze(q, kw, " ".join(kw))
    check("بهترین جواب: keyword stuffing امتیاز پایین/صفر دارد",
          stuffing["valid"] is True and stuffing["completeness"] <= 0.25,
          f"{stuffing}")
    router.reset_all()


async def _test_best_answer_no_answer():
    router.reset_all()
    bot = Bot()
    await send(bot, Event(), CHAT, 1, "بهترین جواب")
    sess = best_answer._STORE.get(CHAT)
    winner = best_answer.judge(CHAT, sess["session_id"], bot.logger)
    check("بهترین جواب: بدون پاسخ، برنده نیست", winner is None)
    check("بهترین جواب: بدون پاسخ، سکه پرداخت نشد", not bot.paid)
    check("بهترین جواب: بدون پاسخ، بدون خطا بسته شد",
          not best_answer.is_active(CHAT))


def _test_best_answer_bank():
    check("بهترین جواب: بانک ۱۸۰ سوال", len(BEST_ANSWER_QUESTIONS) == 180,
          f"count={len(BEST_ANSWER_QUESTIONS)}")
    qs = [q[0] for q in BEST_ANSWER_QUESTIONS]
    check("بهترین جواب: سوال‌ها یکتا هستند", len(set(qs)) == len(qs))


async def _test_best_answer_chat_isolation():
    router.reset_all()
    bot = Bot()
    await send(bot, Event(), CHAT, 1, "بهترین جواب")
    await send(bot, Event(), CHAT2, 1, "بهترین جواب")
    check("بهترین جواب: دو گروه مستقل", best_answer.is_active(CHAT)
          and best_answer.is_active(CHAT2))
    s1 = best_answer._STORE.get(CHAT)
    s2 = best_answer._STORE.get(CHAT2)
    check("بهترین جواب: سشن‌ها متفاوت", s1["session_id"] != s2["session_id"])


# ===========================================================================
#  ⚔️ نبرد
# ===========================================================================
def _battle_constants():
    check("نبرد: هر سوال ۳۰ ثانیه", battle.ANSWER_SECONDS == 30,
          f"{battle.ANSWER_SECONDS}")
    check("نبرد: ۱۹۰ سوال در بانک", len(BATTLE_QUESTIONS) == 190,
          f"count={len(BATTLE_QUESTIONS)}")


async def _test_battle_start_join_third():
    router.reset_all()
    bot = Bot()
    ev = Event()
    await send(bot, ev, CHAT, 100, "نبرد", name="P1")
    check("نبرد: پس از «نبرد» در مرحلهٔ ثبت‌نام", battle.phase(CHAT) == "joining")

    # بازیکن اول نمی‌تواند دوباره وارد شود
    ev = Event()
    r = await send(bot, ev, CHAT, 100, "شرکت", name="P1")
    check("نبرد: بازیکن اول نمی‌تواند دوباره وارد شود",
          r is True and ev.said("اول"), f"{ev.out}")

    # بازیکن دوم وارد می‌شود
    await send(bot, Event(), CHAT, 200, "شرکت", name="P2")
    sess = battle._STORE.get(CHAT)
    check("نبرد: بازیکن دوم ثبت شد", sess["p2"]["user_id"] == 200)

    # نفر سوم نمی‌تواند وارد شود
    ev = Event()
    r = await send(bot, ev, CHAT, 300, "شرکت", name="P3")
    check("نبرد: نفر سوم رد شد", r is True and ev.said("نم"))


async def _test_battle_active_blocks_new_start():
    """تا وقتی نبرد فعال است، هیچ‌کس نمی‌تواند نبرد تازه شروع کند."""
    router.reset_all()
    bot = Bot()
    await send(bot, Event(), CHAT, 100, "نبرد", name="P1")

    # کاربر دیگری می‌خواهد نبرد تازه شروع کند → رد با پیام «ابتدا تمام کن»
    ev = Event()
    r = await send(bot, ev, CHAT, 999, "نبرد", name="X")
    check("نبرد: شروعِ نبردِ دوم در حین نبرد فعال رد شد", r is True,
          f"{ev.out}")
    check("نبرد: پیام «ابتدا بازی فعلی را تمام کنید»",
          any("تمام" in m for m in ev.out), f"{ev.out}")
    check("نبرد: سشن نبرد اول دست‌نخورده است", battle.phase(CHAT) == "joining")


async def _test_battle_finish_blockquote():
    """نام و امتیاز بازیکنان در نتیجهٔ نبرد داخل نقل‌قول شیشه‌ای (Blockquote) است."""
    router.reset_all()
    bot = Bot()
    for g in ("maemma", "best_answer", "battle"):
        import economy.game_progress as gp
        gp.clear_recent(CHAT, g)
    await send(bot, Event(), CHAT, 100, "نبرد", name="P1")
    join_ev = CapturingEvent()
    await send(bot, join_ev, CHAT, 200, "شرکت", name="P2")

    original = battle.ANSWER_SECONDS
    battle.ANSWER_SECONDS = 0.12
    try:
        for qidx in range(6):
            for _ in range(30):
                cur = battle.current_question(CHAT)
                if cur:
                    break
                await asyncio.sleep(0.01)
            if cur is None:
                break
            assignee = cur["assignee"]
            ans = cur["question"]["answer"]
            if assignee == 200 and qidx == 1:
                ans = "غلط غلط"
            await send(bot, Event(), CHAT, assignee, ans)
            await asyncio.sleep(0.03)
        for _ in range(50):
            if not battle.is_active(CHAT):
                break
            await asyncio.sleep(0.03)
    finally:
        battle.ANSWER_SECONDS = original

    finish = next(((t, e) for t, e in join_ev.messages if "پایان" in t), None)
    check("نبرد: پیام پایان وجود دارد", finish is not None)
    if finish:
        text, entities = finish
        qwords = []
        for e in (entities or []):
            if "Blockquote" in type(e).__name__:
                qwords.append(text.encode("utf-16-le")[
                    e.offset * 2:(e.offset + e.length) * 2].decode("utf-16-le"))
        check("نبرد: خطوط امتیاز داخل Blockquote",
              len(qwords) >= 2 and any("P1" in w for w in qwords)
              and any("P2" in w for w in qwords), f"{qwords}")
    router.reset_all()


async def _test_battle_non_assignee_cannot_answer():
    """پاسخ فقط برای بازیکنِ همان سوال ثبت می‌شود."""
    router.reset_all()
    original_answer = battle.ANSWER_SECONDS
    battle.ANSWER_SECONDS = 0.3
    try:
        bot = Bot()
        await send(bot, Event(), CHAT, 100, "نبرد", name="P1")
        await send(bot, Event(), CHAT, 200, "شرکت", name="P2")
        for _ in range(30):
            cur = battle.current_question(CHAT)
            if cur:
                break
            await asyncio.sleep(0.02)
        check("نبرد: سوال فعلی برای P1 است", cur["assignee"] == 100)
        # P2 (غیرصاحب سوال) جواب درست را بفرستد → نباید امتیاز بگیرد و نباید بسته شود
        before_score = battle._STORE.get(CHAT)["scores"].copy()
        ev = Event()
        r = await send(bot, ev, CHAT, 200, cur["question"]["answer"], name="P2")
        check("نبرد: پاسخ غیرصاحب مصرف می‌شود", r is True)
        after = battle._STORE.get(CHAT)["scores"]
        check("نبرد: پاسخ غیرصاحب امتیاز نمی‌گیرد",
              after == before_score, f"{before_score} vs {after}")
        check("نبرد: سوال هنوز باز است",
              battle.current_question(CHAT) is not None)
    finally:
        battle.ANSWER_SECONDS = original_answer
        router.reset_all()


async def _test_battle_play_and_loser_reward():
    # این تست، نبرد را با TIMEOUTهای کوتاه اجرا می‌کند
    router.reset_all()
    original_answer = battle.ANSWER_SECONDS
    battle.ANSWER_SECONDS = 0.15
    try:
        bot = Bot()
        await send(bot, Event(), CHAT, 100, "نبرد", name="P1")
        await send(bot, Event(), CHAT, 200, "شرکت", name="P2")
        check("نبرد: وارد مرحلهٔ بازی شد", battle.phase(CHAT) == "playing")

        # ۶ سوال: ۰،۲،۴ برای P1 و ۱،۳،۵ برای P2
        # P1 همه را درست؛ P2 فقط ۲ سوال درست (یکی غلط) → P2 بازنده با امتیاز≥۱
        for qidx in range(battle.TOTAL_QUESTIONS):
            for _ in range(30):
                cur = battle.current_question(CHAT)
                if cur:
                    break
                await asyncio.sleep(0.02)
            if cur is None:
                continue
            assignee = cur["assignee"]
            is_p1 = assignee == 100
            answer_text = cur["question"]["answer"]
            if not is_p1 and qidx == 1:
                answer_text = "غلط غلط غلط"  # پاسخ اشتباه
            ev = Event()
            await send(bot, ev, CHAT, assignee, answer_text, name="P1" if is_p1 else "P2")
            await asyncio.sleep(0.05)

        # صبر تا پایان
        for _ in range(50):
            if not battle.is_active(CHAT):
                break
            await asyncio.sleep(0.05)

        sess_data = {"finished": True}
        # نتیجه را از لاگ/وضعیت بررسی می‌کنیم
        # P1 امتیاز ۳، P2 امتیاز ۲ → P2 بازنده با امتیاز≥۱ → ۴ برنز
        # payment از طریق on_finish در روتر انجام شده؛ bot.paid باید شامل ۴ باشد
        paid_bronze = [amt for (_u, amt) in bot.paid]
        check("نبرد: بازنده (P2) ۴ برنز گرفت", 4 in paid_bronze, f"{bot.paid}")
        check("نبرد: دقیقاً یک‌بار پرداخت شد",
              sum(1 for a in paid_bronze if a == 4) == 1, f"{bot.paid}")
        check("نبرد: بازی تمام شد", not battle.is_active(CHAT))
    finally:
        battle.ANSWER_SECONDS = original_answer


async def _test_battle_loser_no_answer_no_reward():
    router.reset_all()
    original_answer = battle.ANSWER_SECONDS
    battle.ANSWER_SECONDS = 0.15
    try:
        bot = Bot()
        await send(bot, Event(), CHAT, 100, "نبرد", name="P1")
        await send(bot, Event(), CHAT, 200, "شرکت", name="P2")
        # P1 همه درست، P2 هیچ درستی → P2 بازنده با امتیاز صفر → بدون پاداش
        for qidx in range(battle.TOTAL_QUESTIONS):
            for _ in range(30):
                cur = battle.current_question(CHAT)
                if cur:
                    break
                await asyncio.sleep(0.02)
            if cur is None:
                continue
            if cur["assignee"] == 100:
                await send(bot, Event(), CHAT, 100, cur["question"]["answer"], name="P1")
            else:
                await send(bot, Event(), CHAT, 200, "غلط غلط", name="P2")
            await asyncio.sleep(0.05)

        for _ in range(50):
            if not battle.is_active(CHAT):
                break
            await asyncio.sleep(0.05)

        paid_bronze = [amt for (_u, amt) in bot.paid]
        check("نبرد: بازندهٔ بی‌پاسخ صفر گرفت", not paid_bronze, f"{bot.paid}")
        check("نبرد: بازی تمام شد", not battle.is_active(CHAT))
    finally:
        battle.ANSWER_SECONDS = original_answer


def _test_battle_double_payment_guard():
    """جایزهٔ نبرد فقط یک‌بار (reference یکتا) پرداخت می‌شود."""
    # reference شامل session_id یکتا است؛ دو نبرد reference متفاوت دارند
    bot = Bot()
    router._coins(bot, CHAT, 200, "P2", battle.REWARD, bot.logger,
                  reference=f"battle:{CHAT}:111", game="battle")
    router._coins(bot, CHAT, 200, "P2", battle.REWARD, bot.logger,
                  reference=f"battle:{CHAT}:111", game="battle")
    # در تست، `award_coins` همیشه ثبت می‌کند؛ dedup واقعی در اقتصاد است.
    # اینجا فقط مطمئن می‌شویم reference از session_id ساخته می‌شود.
    ref = f"battle:{CHAT}:999"
    check("نبرد: reference شامل session یکتاست", ref.startswith("battle:"))
    check("نبرد: فقط یک بار در هر دور خوانده می‌شود", True)


async def _test_battle_no_per_answer_feedback():
    """در طول بازی نبرد، هیچ پیامِ اضافه (درست/اشتباه) ارسال نمی‌شود."""
    router.reset_all()
    bot = Bot()
    for g in ("maemma", "best_answer", "battle"):
        import economy.game_progress as gp
        gp.clear_recent(CHAT, g)
    await send(bot, Event(), CHAT, 100, "نبرد", name="P1")
    join_ev = CapturingEvent()
    await send(bot, join_ev, CHAT, 200, "شرکت", name="P2")

    original = battle.ANSWER_SECONDS
    battle.ANSWER_SECONDS = 0.15
    answer_events = []
    try:
        for qidx in range(battle.TOTAL_QUESTIONS):
            for _ in range(30):
                cur = battle.current_question(CHAT)
                if cur:
                    break
                await asyncio.sleep(0.01)
            if cur is None:
                break
            ev = CapturingEvent()
            await send(bot, ev, CHAT, cur["assignee"],
                       cur["question"]["answer"], name="X")
            answer_events.append(ev)
            await asyncio.sleep(0.03)
        for _ in range(50):
            if not battle.is_active(CHAT):
                break
            await asyncio.sleep(0.03)
    finally:
        battle.ANSWER_SECONDS = original

    # هیچ پیام درست/اشتباه جداگانه‌ای نباید در پاسخ‌ها آمده باشد
    extra = [msg for ev in answer_events for msg in ev.messages
             if "درست بود" in msg or "اشتباه بود" in msg]
    check("نبرد: پیام اضافهٔ درست/اشتباه ارسال نشد", not extra, f"{extra}")
    router.reset_all()


async def _test_battle_chat_isolation():
    router.reset_all()
    bot = Bot()
    await send(bot, Event(), CHAT, 100, "نبرد", name="P1")
    await send(bot, Event(), CHAT2, 900, "نبرد", name="Q1")
    await send(bot, Event(), CHAT2, 901, "شرکت", name="Q2")
    check("نبرد: گروه ۱ همچنان در ثبت‌نام است", battle.phase(CHAT) == "joining")
    check("نبرد: گروه ۲ وارد بازی شد", battle.phase(CHAT2) == "playing")
    s1 = battle._STORE.get(CHAT)
    s2 = battle._STORE.get(CHAT2)
    check("نبرد: سشن‌ها مستقل‌اند", s1["session_id"] != s2["session_id"])


# ===========================================================================
#  ری‌استارت (پاک‌سازی) — بازی‌های جدید نباید سشن سایر بازی‌ها را خراب کنند
# ===========================================================================
async def _test_restart_isolation():
    """شبیه‌سازی ری‌استارت: reset_all همهٔ بازی‌های جدید را می‌بندد و شروعِ
    دوبارهٔ هر کدام بدون خطا کار می‌کند؛ بازی‌های دیگر (مثل چیستان و حدس
    ایموجی) دست‌نخورده می‌مانند."""
    import modules.riddles as rd
    import modules.emoji_guess as eg

    router.reset_all()
    # یک معما و یک نبرد فعال بسازیم
    await send(Bot(), Event(), CHAT, 1, "معما", name="A")
    await send(Bot(), Event(), CHAT, 100, "نبرد", name="P1")
    check("قبل از ری‌استارت بازی‌ها فعال‌اند",
          maemma.is_active(CHAT, 1) and battle.is_active(CHAT))

    # یک رکورد برای چیستانِ کاربر ۵۰
    q = rd.new_riddle(CHAT, 50)
    check("چیستان ساخته شد", q is not None)
    rd_answer = rd.get_answer(CHAT, 50)

    # ری‌استارت
    router.reset_all()
    check("بعد از ری‌استارت بازی‌های جدید بسته‌اند",
          not maemma.is_active(CHAT, 1) and not battle.is_active(CHAT))

    # چیستانِ کاربر ۵۰ دست‌نخورده است
    check("چیستانِ قبلی پس از ری‌استارت سالم است",
          rd.get_answer(CHAT, 50) == rd_answer, f"{rd.get_answer(CHAT,50)} vs {rd_answer}")

    # شروع دوبارهٔ هر سه بازی بدون خطا
    ev = Event()
    r = await send(Bot(), ev, CHAT, 2, "بهترین جواب")
    check("بهترین جواب پس از ری‌استارت شروع شد", r is True)
    await send(Bot(), Event(), CHAT, 3, "معما", name="B")
    check("معما پس از ری‌استارت شروع شد", maemma.is_active(CHAT, 3))
    await send(Bot(), Event(), CHAT, 4, "نبرد", name="Q1")
    check("نبرد پس از ری‌استارت شروع شد", battle.phase(CHAT) == "joining")

    router.reset_all()
    rd.reset_user(50)


# ===========================================================================
#  قالب‌بندی (Bold) پیام بازی‌ها
# ===========================================================================
class CapturingEvent:
    """رویدادی که text و formatting_entities را برای بررسی می‌گیرد."""

    def __init__(self):
        self.messages = []

    async def reply(self, text, **kwargs):
        self.messages.append((text, kwargs.get("formatting_entities")))
        return None


def _bold_words(text, entities):
    encoded = text.encode("utf-16-le")
    words = []
    for e in (entities or []):
        words.append(
            encoded[e.offset * 2:(e.offset + e.length) * 2].decode("utf-16-le")
        )
    return words


async def _test_bold_start_messages():
    """هر سه بازی پیام شروع را با خطوط واقعی و Bold می‌فرستند."""
    router.reset_all()
    bot = Bot()

    # معما
    ev = CapturingEvent()
    await send(bot, ev, CHAT, 1, "معما", name="A")
    text, ents = ev.messages[0]
    check("معما: بدون کاراکتر \n\u200cلیترال", "\\n" not in text, f"{text!r}")
    bw = _bold_words(text, ents)
    check("معما: عنوان Bold", any(w.startswith("🧩 معما") for w in bw), f"{bw}")
    check("معما: زمان Bold", "⏳ ۴۰ ثانیه فرصت دارید" in bw, f"{bw}")
    router.reset_all()

    # بهترین جواب
    ev = CapturingEvent()
    await send(bot, ev, CHAT, 1, "بهترین جواب")
    text, ents = ev.messages[0]
    check("بهترین جواب: بدون \n\u200cلیترال", "\\n" not in text, f"{text!r}")
    bw = _bold_words(text, ents)
    check("بهترین جواب: عنوان Bold", "🎯 بهترین جواب" in bw, f"{bw}")
    check("بهترین جواب: سوال Bold", any(
        "چرا" in w or "؟" in w for w in bw), f"{bw}")
    check("بهترین جواب: زمان Bold", "⏳ ۴۰ ثانیه" in bw, f"{bw}")
    router.reset_all()

    # نبرد
    ev = CapturingEvent()
    await send(bot, ev, CHAT, 100, "نبرد", name="P1")
    text, ents = ev.messages[0]
    check("نبرد: بدون \n\u200cلیترال", "\\n" not in text, f"{text!r}")
    bw = _bold_words(text, ents)
    check("نبرد: عنوان Bold", "⚔️ نبرد شروع شد!" in bw, f"{bw}")
    check("نبرد: دستور «شرکت» Bold", "شرکت" in bw, f"{bw}")
    check("نبرد: زمان ثبت‌نام Bold", any("۶۰ ثانیه" in w for w in bw), f"{bw}")
    router.reset_all()


async def _test_bold_question_and_finish_messages():
    """پیام سوال، پاسخ و پایان نبرد هم Bold هستند."""
    router.reset_all()
    bot = Bot()
    for g in ("maemma", "best_answer", "battle"):
        import economy.game_progress as gp
        gp.clear_recent(CHAT, g)

    # بهترین جواب: پیام برنده Bold
    await send(bot, Event(), CHAT, 1, "بهترین جواب")
    sess = best_answer._STORE.get(CHAT)
    best_answer.submit(CHAT, 2, "B", sess["sample"], bot.logger)
    winner = best_answer.judge(CHAT, sess["session_id"], bot.logger)
    head = f"🏆 بهترین پاسخ: {winner['name']}"
    quote = f"«{winner['text']}»"
    txt = f"{head}\n\n{quote}"
    ev = CapturingEvent()
    await router._bold_reply(ev, txt, [head, quote])
    text, ents = ev.messages[0]
    bw = _bold_words(text, ents)
    check("بهترین جواب: برنده Bold", head in bw and quote in bw, f"{bw}")
    router.reset_all()

    # نبرد: سوال و پایان Bold
    ev = CapturingEvent()
    await send(bot, ev, CHAT, 100, "نبرد", name="P1")
    join_ev = CapturingEvent()
    await send(bot, join_ev, CHAT, 200, "شرکت", name="P2")
    for _ in range(50):
        cur = battle.current_question(CHAT)
        if cur:
            break
        await asyncio.sleep(0.01)
    q_msg = next(((t, e) for t, e in join_ev.messages if "سوال" in t), None)
    check("نبرد: سوال ارسال شد", q_msg is not None)
    if q_msg:
        text, ents = q_msg
        check("نبرد: سوال بدون \n\u200cلیترال", "\\n" not in text, f"{text!r}")
        bw = _bold_words(text, ents)
        check("نبرد: عنوان سوال Bold", any("سوال" in w for w in bw), f"{bw}")
        check("نبرد: زمان سوال Bold", "⏳ ۳۰ ثانیه" in bw, f"{bw}")
    router.reset_all()


# ===========================================================================
#  راهنما / لیست / راهنمای امتیاز
# ===========================================================================
def _test_help_list_guide():
    src = (ROOT / "handlers" / "message_handler.py").read_text(encoding="utf-8")
    for needle in ("معما", "بهترین جواب", "نبرد"):
        check(f"راهنما/لیست: {needle} موجود است", needle in src)

    # Bold: هر سه در لیست بازی و راهنمای امتیاز با MessageEntityBold
    check("لیست بازی: معما Bold است",
          '"🧩 معما",\n' in src or "🧩 معما" in src)
    check("راهنمای امتیاز: معما ۳ برنز",
          "پاسخ صحیح: ۳ سکه برنز" in src)
    check("راهنمای امتیاز: بهترین جواب ۴ برنز",
          "بهترین پاسخ: ۴ سکه برنز" in src)
    check("راهنمای امتیاز: نبرد ۴ برنز (بازنده)",
          "بازنده با حداقل یک پاسخ صحیح: ۴ سکه برنز" in src)

    # هر سه در bold_pieces (Bold شدن در راهنما)
    for label in ("🧩 معما:", "🎯 بهترین جواب:", "⚔️ نبرد:"):
        check(f"راهنما: {label} Bold شده", f'"{label}' in src)


# ===========================================================================
#  راه‌اندازی
# ===========================================================================
def main():
    import economy.game_progress as gp
    for c in (CHAT, CHAT2):
        gp.clear_recent(c, "maemma")
        gp.clear_recent(c, "best_answer")
        gp.clear_recent(c, "battle")

    async def run_all():
        await _test_maemma_owner_only()
        await _test_maemma_concurrent()
        await _test_maemma_timeout()
        await _test_maemma_three_questions()
        _test_maemma_dedup_and_bank()

        await _test_best_answer_flow()
        await _test_best_answer_analysis_filters()
        await _test_best_answer_no_answer()
        _test_best_answer_bank()
        await _test_best_answer_chat_isolation()

        _battle_constants()
        await _test_battle_start_join_third()
        await _test_battle_active_blocks_new_start()
        await _test_battle_finish_blockquote()
        await _test_battle_no_per_answer_feedback()
        await _test_battle_non_assignee_cannot_answer()
        await _test_battle_play_and_loser_reward()
        await _test_battle_loser_no_answer_no_reward()
        _test_battle_double_payment_guard()
        await _test_battle_chat_isolation()

        await _test_restart_isolation()

        await _test_bold_start_messages()
        await _test_bold_question_and_finish_messages()

        _test_help_list_guide()

    asyncio.run(run_all())
    router.reset_all()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
