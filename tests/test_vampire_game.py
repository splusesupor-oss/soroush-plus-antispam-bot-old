"""🧛 خون‌آشام — دیباگ کامل مسیر بازی، با تمرکز روی پیام خصوصی.

ریشهٔ باگ «پیام خصوصی ارسال نمی‌شود»:
    بازی فقط ``user_id`` عددی را نگه می‌داشت و همان int را به
    ``client.send_message`` می‌داد. splusthon اول ``utils.get_input_peer(int)``
    را صدا می‌زند که همیشه ``TypeError`` می‌دهد، بعد سراغ کش می‌رود. نشست از
    نوع ``StringSession`` است و کش آن فقط در RAM زندگی می‌کند، پس بعد از هر
    ری‌استارت خالی است و resolve با ``ValueError`` شکست می‌خورد. حساب هم
    userbot است، بنابراین مسیر ویژهٔ ``access_hash=0`` مخصوص bot ها هم در
    دسترس نیست. خطا داخل ``except`` بی‌صدا بلعیده می‌شد و بازی ادامه پیدا
    می‌کرد.

    این دقیقاً توضیح می‌دهد چرا قابلیت «بدون تغییر کد» خراب شد: تا وقتی
    پروسه بالا بود کش پر بود و پیوی می‌رفت؛ بعد از ری‌استارت کش خالی شد.

    python tests/test_vampire_game.py
"""
import asyncio
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from splusthon import utils
from splusthon.tl import types

import handlers.fox_games_router as router
from modules.fox_games import vampire as vp

PASSED = FAILED = 0
CHAT = -880001


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


def make_user(uid, name, access_hash=999):
    """شیء کاربر واقعی splusthon، همان چیزی که event.get_sender() می‌دهد."""
    return types.User(id=uid, user_type=None, access_hash=access_hash,
                      first_name=name)


class RealisticClient:
    """resolve را دقیقاً مثل splusthon انجام می‌دهد.

    یک ``int`` فقط وقتی کار می‌کند که در کش باشد؛ شیء ``User`` دارای
    ``access_hash`` همیشه بدون کش و بدون شبکه resolve می‌شود.
    """

    def __init__(self, cache=None, fail_all=False):
        self.entity_cache = dict(cache or {})
        self.sent = []
        self.fail_all = fail_all

    async def send_message(self, target, text, **kwargs):
        if self.fail_all:
            raise ValueError("Could not find the input entity")
        try:
            peer = utils.get_input_peer(target)
        except TypeError:
            if isinstance(target, int):
                if target not in self.entity_cache:
                    raise ValueError(
                        f"Could not find input entity with key {target}")
                peer = types.InputPeerUser(target, self.entity_cache[target])
            else:
                raise
        self.sent.append((peer, text))
        return True


class Event:
    def __init__(self):
        self.out = []

    async def reply(self, text, **kwargs):
        self.out.append(text)
        return None

    def said(self, needle):
        return any(needle in m for m in self.out)


class SpoilerEvent(Event):
    """مثل Event ولی entityهای هر پیام را هم نگه می‌دارد."""

    def __init__(self):
        super().__init__()
        self.entities = []

    async def reply(self, text, **kwargs):
        self.entities.append(kwargs.get("formatting_entities"))
        return await super().reply(text, **kwargs)


class Logger:
    def __init__(self):
        self.info, self.errors = [], []

    def log_info(self, m):
        self.info.append(m)

    def log_error(self, m):
        self.errors.append(m)

    def has(self, needle):
        return any(needle in m for m in self.info + self.errors)

    def has_error(self, needle):
        return any(needle in m for m in self.errors)


class Bot:
    def __init__(self, client=None):
        self.client = client or RealisticClient()
        self.logger = Logger()
        self.paid = []

    def award_coins(self, chat_id, user_id, name, amount):
        self.paid.append((user_id, amount))
        return amount


async def send(bot, event, uid, text, name=None):
    return await router.handle(
        bot, event, CHAT, uid, make_user(uid, name or f"P{uid}"),
        text, bot.logger,
    )


def seed(logger, count=4, access_hash=999):
    """یک بازی با ``count`` بازیکن ثبت‌نام‌شده."""
    vp.reset_all()
    vp.start(CHAT, logger)
    for uid in range(101, 101 + count):
        vp.join(CHAT, uid, make_user(uid, f"P{uid}", access_hash), logger)


# ===========================================================================
# ریشهٔ باگ
# ===========================================================================
def test_bare_int_cannot_resolve():
    print("\n### 🔍 ریشهٔ باگ: int خام قابل resolve نیست")
    raised = False
    try:
        utils.get_input_peer(101)
    except TypeError:
        raised = True
    check("get_input_peer روی int خام TypeError می‌دهد", raised)

    user = make_user(101, "علی")
    peer = utils.get_input_peer(user)
    check("شیء User مستقیماً به InputPeerUser تبدیل می‌شود",
          isinstance(peer, types.InputPeerUser) and peer.user_id == 101)
    check("access_hash حفظ می‌شود", peer.access_hash == 999)

    from splusthon.sessions import StringSession
    session = StringSession()
    check("کش StringSession پس از ری‌استارت خالی است",
          len(session._entities) == 0)
    missing = False
    try:
        session.get_input_entity(101)
    except ValueError:
        missing = True
    check("int خام روی نشست تازه ValueError می‌دهد", missing)


def test_join_stores_peer():
    print("\n### 🔍 ثبت‌نام شیء کاربر را نگه می‌دارد")
    logger = Logger()
    seed(logger)
    players = vp._STORE.get(CHAT)["players"]
    check("همهٔ بازیکنان peer دارند",
          all(p.get("peer") is not None for p in players))
    check("peer قابل تبدیل به InputPeer است",
          all(isinstance(utils.get_input_peer(p["peer"]), types.InputPeerUser)
              for p in players))
    check("ثبت peer در لاگ آمده", logger.has("has_peer=True"))
    vp.reset_all()


def test_dm_succeeds_with_cold_cache():
    """گارد رگرسیون اصلی: با کش خالی هم پیوی باید برود."""
    print("\n### 🩸 ارسال پیوی با کش کاملاً خالی")
    logger = Logger()
    seed(logger)
    chosen = vp.choose_vampire(CHAT, logger)
    client = RealisticClient(cache={})       # کش خالی، مثل بعد از ری‌استارت

    ok, error = asyncio.run(
        vp.send_role_dm(client, chosen["player"], logger=logger, chat_id=CHAT))
    check("ارسال پیوی موفق بود", ok is True, f"-> {error!r}")
    check("دقیقاً یک پیام ارسال شد", len(client.sent) == 1)
    check("گیرنده InputPeerUser درست است",
          client.sent[0][0].user_id == chosen["player"]["user_id"])
    check("متن نقش درست است", client.sent[0][1] == vp.ROLE_MESSAGE)
    check("ارسال موفق لاگ شد", logger.has("ROLE DM SENT"))
    check("مسیر استفاده‌شده peer_object بود", logger.has("via=peer_object"))
    vp.reset_all()


def test_old_behaviour_would_fail():
    """اثبات اینکه کد قدیمی (فقط int) واقعاً شکست می‌خورد."""
    print("\n### 🔍 بازتولید رفتار قدیمی")
    logger = Logger()
    seed(logger)
    chosen = vp.choose_vampire(CHAT, logger)

    legacy = dict(chosen["player"])
    legacy["peer"] = None                     # همان کاری که کد قدیمی می‌کرد
    client = RealisticClient(cache={})
    ok, error = asyncio.run(
        vp.send_role_dm(client, legacy, logger=logger, chat_id=CHAT))
    check("با شناسهٔ عددی و کش خالی ارسال شکست می‌خورد", ok is False)
    check("خطا از نوع ValueError است", isinstance(error, ValueError),
          f"-> {error!r}")
    check("شکست در لاگ خطا ثبت شد", logger.has_error("ROLE DM FAILED"))
    check("هیچ پیامی ارسال نشد", client.sent == [])
    vp.reset_all()


def test_dm_failure_never_cancels_game():
    """درخواست کاربر: نبود چت خصوصی نباید بازی را متوقف کند.

    رفتار قبلی بازی را لغو می‌کرد و می‌گفت «کاربر باید یک بار به ربات
    پیام خصوصی بدهد» — که در گروه عملاً یعنی بازی هرگز شروع نمی‌شود.
    """
    print("\n### 🩸 شکست پیوی بازی را لغو نمی‌کند")

    async def scenario():
        router.reset_all()
        bot = Bot(RealisticClient(fail_all=True))
        event = SpoilerEvent()
        await send(bot, event, 1, "خون آشام")
        # ظرفیت کامل می‌شود تا پنجرهٔ ۶۰ ثانیه‌ای ثبت‌نام بلافاصله بسته شود.
        for uid in range(11, 11 + vp.MAX_PLAYERS):
            await send(bot, event, uid, "شرکت")
        await asyncio.sleep(0.6)
        # وضعیت باید *داخل* همین حلقه خوانده شود: پایان ``asyncio.run``
        # تسک بازی را cancel می‌کند و بند ``finally`` جلسه را می‌بندد،
        # پس خواندن بعد از آن همیشه False می‌دهد و ربطی به محصول ندارد.
        return bot, event, vp.is_active(CHAT), vp.phase(CHAT)

    bot, event, active, phase = asyncio.run(scenario())
    check("بازی لغو نشد و هنوز فعال است", active)
    check("مرحلهٔ حدس باز شد", phase == "guessing", f"-> {phase}")
    check("پیام «بازی لغو شد» داده نشد",
          not event.said("بازی لغو شد"))
    check("از کاربر درخواست پیوی دستی نشد",
          not event.said("یک بار به ربات پیام خصوصی"))
    check("نقش از راه جایگزین داخل گروه اعلام شد",
          event.said(vp.SECRET_FALLBACK_HEADER))
    check("فهرست بازیکنان نمایش داده شد", event.said("1."))
    check("تلاش ناموفق پیوی لاگ شد", bot.logger.has_error("ROLE DM FAILED"))
    check("استفاده از مسیر جایگزین لاگ شد",
          bot.logger.has("ROLE SECRET SENT"))
    check("هیچ سکه‌ای بدون حدس درست پرداخت نشد", bot.paid == [])
    router.reset_all()


def test_secret_fallback_hides_the_name():
    """نام خون‌آشام باید پشت اسپویلر باشد، نه متن ساده."""
    print("\n### 🕶 نام خون‌آشام پشت اسپویلر پنهان می‌شود")
    player = {"name": "علی رضایی", "user_id": 7}
    text, spans = vp.secret_role_message(player)

    check("نام داخل متن هست", "علی رضایی" in text)
    check("دقیقاً یک بازهٔ اسپویلر تولید شد", len(spans) == 1, f"-> {spans}")
    kind, offset, length = spans[0]
    check("نوع بازه spoiler است", kind == "spoiler")

    # offset باید بر حسب UTF-16 باشد وگرنه روی متن فارسی می‌لغزد.
    buf = text.encode("utf-16-le")
    covered = buf[offset * 2:(offset + length) * 2].decode("utf-16-le")
    check("بازه دقیقاً روی نام می‌افتد", covered == "علی رضایی",
          f"-> {covered!r}")
    check("راهنما برای بقیه هست", vp.SECRET_FALLBACK_HINT in text)


def test_secret_fallback_entities_are_real():
    """روتر باید span را به MessageEntitySpoiler واقعی تبدیل کند."""
    print("\n### 🕶 entity واقعی اسپویلر ساخته می‌شود")
    from splusthon.tl.types import MessageEntitySpoiler

    _text, spans = vp.secret_role_message({"name": "حسین", "user_id": 3})
    entities = router._spoiler_entities(spans)
    check("یک entity ساخته شد", len(entities) == 1, f"-> {entities}")
    check("از نوع MessageEntitySpoiler است",
          isinstance(entities[0], MessageEntitySpoiler))
    check("offset منتقل شد", entities[0].offset == spans[0][1])
    check("length منتقل شد", entities[0].length == spans[0][2])
    check("span غیر اسپویلر نادیده گرفته می‌شود",
          router._spoiler_entities([("bold", 0, 3)]) == [])


def test_dm_preferred_when_available():
    """اگر پیوی ممکن باشد، همان استفاده شود و چیزی در گروه لو نرود."""
    print("\n### 🩸 وقتی پیوی ممکن است، مسیر جایگزین استفاده نمی‌شود")

    async def scenario():
        router.reset_all()
        bot = Bot()                       # پیوی سالم
        event = SpoilerEvent()
        await send(bot, event, 1, "خون آشام")
        for uid in range(41, 41 + vp.MAX_PLAYERS):
            await send(bot, event, uid, "شرکت")
        await asyncio.sleep(0.6)
        return bot, event, vp.is_active(CHAT)

    bot, event, active = asyncio.run(scenario())
    check("پیوی ارسال شد", len(bot.client.sent) == 1)
    check("نقش در گروه اعلام نشد",
          not event.said(vp.SECRET_FALLBACK_HEADER))
    check("پیام اعلام معمولی داده شد", event.said(vp.CHOSEN_MESSAGE))
    check("هیچ entity اسپویلری فرستاده نشد",
          all(not e for e in event.entities))
    check("بازی فعال است", active)
    router.reset_all()


def test_deliver_role_modes():
    """قرارداد ``deliver_role``: dm / secret / failed."""
    print("\n### 🩸 حالت‌های سه‌گانهٔ رساندن نقش")
    logger = Logger()
    seed(logger)
    chosen = vp.choose_vampire(CHAT, logger)
    player = chosen["player"]

    sent = []

    async def secret(text, spans):
        sent.append((text, spans))

    mode = asyncio.run(vp.deliver_role(
        RealisticClient(), player, logger=logger, chat_id=CHAT,
        send_secret=secret))
    check("پیوی سالم -> dm", mode == "dm", f"-> {mode}")
    check("مسیر جایگزین صدا نشد", sent == [])

    mode = asyncio.run(vp.deliver_role(
        RealisticClient(fail_all=True), player, logger=logger, chat_id=CHAT,
        send_secret=secret))
    check("پیوی خراب -> secret", mode == "secret", f"-> {mode}")
    check("پیام مخفی ارسال شد", len(sent) == 1)

    async def broken(_text, _spans):
        raise RuntimeError("group send blocked")

    mode = asyncio.run(vp.deliver_role(
        RealisticClient(fail_all=True), player, logger=logger, chat_id=CHAT,
        send_secret=broken))
    check("هر دو مسیر خراب -> failed", mode == "failed", f"-> {mode}")

    mode = asyncio.run(vp.deliver_role(
        RealisticClient(fail_all=True), player, logger=logger, chat_id=CHAT,
        send_secret=None))
    check("بدون مسیر جایگزین -> failed", mode == "failed", f"-> {mode}")
    vp.reset_all()


def test_guessing_works_after_fallback():
    """بعد از اعلام مخفی، بازی واقعاً قابل بازی است و جایزه می‌دهد."""
    print("\n### 🩸 بازی بعد از مسیر جایگزین کامل انجام می‌شود")

    async def scenario():
        router.reset_all()
        bot = Bot(RealisticClient(fail_all=True))
        event = SpoilerEvent()
        await send(bot, event, 1, "خون آشام")
        for uid in range(51, 51 + vp.MAX_PLAYERS):
            await send(bot, event, uid, "شرکت")
        await asyncio.sleep(0.6)

        vampire_uid = vp.vampire_player(CHAT)["user_id"]
        players = vp._STORE.get(CHAT)["players"]
        number = next(i for i, p in enumerate(players, 1)
                      if p["user_id"] == vampire_uid)
        guesser = next(p["user_id"] for p in players
                       if p["user_id"] != vampire_uid)
        await send(bot, event, guesser, str(number))
        return bot, event

    bot, event = asyncio.run(scenario())
    check("حدس درست پذیرفته شد", bot.paid != [], f"-> {bot.paid}")
    check("جایزه ۷ سکه بود", bot.paid and bot.paid[0][1] == vp.WINNER_COINS,
          f"-> {bot.paid}")
    check("بازی پس از برد بسته شد", not vp.is_active(CHAT))
    router.reset_all()


def test_no_guessing_before_dm():
    print("\n### 🩸 پیش از ارسال پیوی هیچ حدسی پذیرفته نمی‌شود")
    logger = Logger()
    seed(logger)
    chosen = vp.choose_vampire(CHAT, logger)
    check("مرحله پس از انتخاب، assigning است",
          vp.phase(CHAT) == "assigning", f"-> {vp.phase(CHAT)}")
    state, _ = vp.guess(CHAT, 102, "1", logger)
    check("حدس در مرحلهٔ assigning رد می‌شود", state == "closed", f"-> {state}")

    check("open_guessing مرحله را باز می‌کند",
          vp.open_guessing(CHAT, logger=logger) is True)
    check("اکنون مرحله guessing است", vp.phase(CHAT) == "guessing")
    check("open_guessing دوباره کار نمی‌کند",
          vp.open_guessing(CHAT, logger=logger) is False)
    check("باز شدن مرحله لاگ شد", logger.has("GUESSING OPEN"))
    vp.reset_all()


# ===========================================================================
# پیام‌های گروه
# ===========================================================================
def test_group_messages_exact():
    print("\n### 💬 متن دقیق پیام‌های گروه")
    check("متن اعلام ارسال پیوی دقیقاً مطابق خواسته است",
          vp.CHOSEN_MESSAGE == (
              "🩸 پیام خصوصی خون‌آشام برای یکی از بازیکنان ارسال شد. "
              "حالا حدس بزنید خون‌آشام کیست!"
          ), f"-> {vp.CHOSEN_MESSAGE}")

    players = [{"name": n} for n in ("علی", "حسین", "محمد", "میلاد", "رضا")]
    roster = vp.roster_lines(players)
    check("فهرست دقیقاً نام‌ها را با شماره لاتین می‌دهد",
          roster == "1. علی\n2. حسین\n3. محمد\n4. میلاد\n5. رضا",
          f"-> {roster!r}")


def test_full_flow_messages():
    print("\n### 💬 مسیر کامل: پیام‌ها به ترتیب درست")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "خون آشام")
        for uid in range(21, 21 + vp.MAX_PLAYERS):
            await send(bot, event, uid, "شرکت")
        await asyncio.sleep(0.6)
        return bot, event

    bot, event = asyncio.run(scenario())
    check("پیام اعلام ارسال پیوی نمایش داده شد",
          event.said("🩸 پیام خصوصی خون‌آشام برای یکی از بازیکنان ارسال شد"))
    check("فهرست شماره‌دار نمایش داده شد", event.said("1."))
    check("دقیقاً یک پیام خصوصی ارسال شد", len(bot.client.sent) == 1,
          f"-> {len(bot.client.sent)}")
    check("متن پیوی متن نقش است",
          bot.client.sent[0][1] == vp.ROLE_MESSAGE)

    order_dm = next(i for i, m in enumerate(event.out)
                    if "🩸 پیام خصوصی" in m)
    order_roster = next(i for i, m in enumerate(event.out) if m.startswith("1."))
    check("فهرست بعد از پیام اعلام می‌آید", order_roster > order_dm)
    router.reset_all()


# ===========================================================================
# قوانین بازی
# ===========================================================================
def test_rules():
    print("\n### 📏 قوانین بازی")
    check("زمان حدس دقیقاً ۵۰ ثانیه است", vp.GUESS_SECONDS == 50)
    check("جایزهٔ حدس درست ۷ سکه است", vp.WINNER_COINS == 7)

    logger = Logger()
    seed(logger, count=5)
    chosen = vp.choose_vampire(CHAT, logger)
    vp.open_guessing(CHAT, logger=logger)
    players = vp._STORE.get(CHAT)["players"]
    vampire_uid = chosen["player"]["user_id"]
    number = chosen["number"]

    check("غیر شرکت‌کننده نمی‌تواند حدس بزند",
          vp.guess(CHAT, 999, str(number), logger)[0] == "not_player")
    check("خون‌آشام نمی‌تواند حدس بزند",
          vp.guess(CHAT, vampire_uid, str(number), logger)[0] == "is_vampire")
    check("نوبت خون‌آشام مصرف نشد",
          vampire_uid not in vp._STORE.get(CHAT)["guessed"])

    guesser = next(p["user_id"] for p in players if p["user_id"] != vampire_uid)
    own = next(i for i, p in enumerate(players, 1) if p["user_id"] == guesser)
    check("کسی نمی‌تواند شمارهٔ خودش را انتخاب کند",
          vp.guess(CHAT, guesser, str(own), logger)[0] == "self_guess")
    check("انتخاب خود نوبت را نمی‌سوزاند",
          guesser not in vp._STORE.get(CHAT)["guessed"])

    wrong = next(i for i in range(1, len(players) + 1)
                 if i not in {number, own})
    check("حدس غلط ثبت می‌شود",
          vp.guess(CHAT, guesser, str(wrong), logger)[0] == "wrong")
    check("حدس دوم همان بازیکن رد می‌شود",
          vp.guess(CHAT, guesser, str(number), logger)[0] == "already")

    winner = next(p["user_id"] for p in players
                  if p["user_id"] not in {vampire_uid, guesser})
    state, info = vp.guess(CHAT, winner, str(number), logger)
    check("حدس درست پذیرفته می‌شود", state == "correct", f"-> {state}")
    check("جایزه ۷ سکه است", info["coins"] == 7)
    check("بازی پس از حدس درست بسته شد", not vp.is_active(CHAT))
    vp.reset_all()


def test_restart_blocked():
    print("\n### 📏 اجرای دوباره در حین بازی")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "خون آشام")
        started = vp.is_active(CHAT)
        again = Event()
        await send(bot, again, 2, "خون آشام")
        third = Event()
        await send(bot, third, 3, "خون‌آشام")
        vp._STORE.cancel_task(CHAT)
        return started, again, third

    started, again, third = asyncio.run(scenario())
    check("بازی شروع شد", started)
    check("اجرای دوباره مسدود شد", again.said("همین حالا در جریان"))
    check("شکل با نیم‌فاصله هم مسدود می‌شود",
          third.said("همین حالا در جریان"))
    router.reset_all()


def test_random_selection():
    print("\n### 🎲 انتخاب تصادفی خون‌آشام")
    logger = Logger()
    picks = Counter()
    for _ in range(80):
        seed(logger)
        picks[vp.choose_vampire(CHAT, logger)["player"]["user_id"]] += 1
        vp.abandon(CHAT, logger=logger)
    check("همهٔ بازیکنان شانس انتخاب دارند", len(picks) == 4,
          f"-> {dict(picks)}")
    check("توزیع تک‌نفره نیست", max(picks.values()) < 70,
          f"-> {dict(picks)}")
    vp.reset_all()


def test_timeout_reveals():
    print("\n### ⏰ پایان زمان و افشای خون‌آشام")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        session = vp.start(CHAT, bot.logger)
        for uid in (31, 32, 33, 34):
            vp.join(CHAT, uid, make_user(uid, f"P{uid}"), bot.logger)

        async def on_roles(chosen):
            ok, _ = await vp.send_role_dm(
                bot.client, chosen["player"], logger=bot.logger, chat_id=CHAT)
            return ok

        async def on_roster(chosen):
            await event.reply(vp.CHOSEN_MESSAGE)
            await event.reply(vp.roster_lines(chosen["players"]))

        async def on_timeout(revealed):
            await event.reply(vp.format_reveal(revealed))

        async def noop(*_):
            return None

        vp.schedule(CHAT, session["session_id"], {
            "on_abort": noop, "on_roles": on_roles, "on_roster": on_roster,
            "on_dm_failed": noop, "on_timeout": on_timeout,
        }, logger=bot.logger, join_seconds=0.05, guess_seconds=0.3)
        await asyncio.sleep(0.9)
        return bot, event

    bot, event = asyncio.run(scenario())
    check("پیوی ارسال شد", len(bot.client.sent) == 1)
    check("هویت خون‌آشام در پایان اعلام شد", event.said("🧛 خون‌آشام:"))
    check("پایان پنجرهٔ حدس لاگ شد",
          bot.logger.has("GUESS WINDOW ENDED"))
    check("state پس از پایان پاک شد", not vp.is_active(CHAT))
    check("هیچ سکه‌ای بدون حدس درست پرداخت نشد", bot.paid == [])
    router.reset_all()


# ===========================================================================
# پاک شدن وضعیت و نبود نشتی
# ===========================================================================
def test_state_cleanup():
    print("\n### 🧹 پاک شدن کامل وضعیت بین بازی‌ها")
    logger = Logger()
    seed(logger)
    chosen = vp.choose_vampire(CHAT, logger)
    vp.open_guessing(CHAT, logger=logger)
    players = vp._STORE.get(CHAT)["players"]
    vampire_uid = chosen["player"]["user_id"]
    guesser = next(p["user_id"] for p in players if p["user_id"] != vampire_uid)
    own = next(i for i, p in enumerate(players, 1) if p["user_id"] == guesser)
    wrong = next(i for i in range(1, len(players) + 1)
                 if i not in {chosen["number"], own})
    vp.guess(CHAT, guesser, str(wrong), logger)

    vp.reveal(CHAT, logger=logger)
    check("بازی بسته شد", not vp.is_active(CHAT))
    check("session حذف شد", vp._STORE.get(CHAT) is None)
    check("تایمر باقی نماند", vp._STORE.task_for(CHAT) is None)

    # بازی تازه نباید هیچ ردی از قبلی داشته باشد
    seed(logger)
    fresh = vp._STORE.get(CHAT)
    check("بازی جدید هیچ حدسی از قبل ندارد", fresh["guessed"] == set())
    check("بازی جدید خون‌آشام تعیین‌نشده دارد", fresh["vampire"] is None)
    check("بازی جدید در مرحلهٔ joining است", fresh["phase"] == "joining")
    check("بازیکنان بازی قبلی پاک شدند", len(fresh["players"]) == 4)
    check("شناسهٔ session تازه است",
          fresh["session_id"] != chosen.get("session_id"))
    vp.reset_all()


def test_repeated_games():
    print("\n### 🔁 ده بازی پشت سر هم بدون نشتی")

    async def one_round(index):
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "خون آشام")
        base = 500 + index * 10
        for offset in range(vp.MAX_PLAYERS):
            await send(bot, event, base + offset, "شرکت")
        await asyncio.sleep(0.6)
        return bot, event

    results = []
    for index in range(10):
        results.append(asyncio.run(one_round(index)))

    check("در هر ۱۰ بازی دقیقاً یک پیوی ارسال شد",
          all(len(bot.client.sent) == 1 for bot, _ in results),
          f"-> {[len(b.client.sent) for b, _ in results]}")
    check("در هر ۱۰ بازی پیام اعلام نمایش داده شد",
          all(ev.said("🩸 پیام خصوصی") for _, ev in results))
    check("در هر ۱۰ بازی فهرست نمایش داده شد",
          all(ev.said("1.") for _, ev in results))
    check("هیچ بازی‌ای در پایان فعال نماند", not vp.is_active(CHAT))
    check("هیچ خطای پیوی رخ نداد",
          not any(b.logger.has_error("ROLE DM FAILED") for b, _ in results))
    router.reset_all()


def test_isolation_from_other_games():
    print("\n### 🔒 نبود تداخل با بازی‌های دیگر")
    import modules.emoji_guess as eg
    from modules.fox_games import laugh_or_lose as lol
    from modules.fox_games import lucky_box as lb
    from modules.fox_games import survival as sv

    stores = {"vampire": id(vp._STORE), "laugh": id(lol._STORE),
              "survival": id(sv._STORE), "lucky_box": id(lb._STORE)}
    check("SessionStore خون‌آشام مستقل است", len(set(stores.values())) == 4)

    router.reset_all()
    eg.reset_all()
    logger = Logger()
    seed(logger)
    lol.start(CHAT)
    sv.start(CHAT)
    eg.start(CHAT, 1)
    check("همه هم‌زمان فعالند",
          vp.is_active(CHAT) and lol.is_active(CHAT) and sv.is_active(CHAT))

    lol.reset_all(CHAT)
    sv.reset_all(CHAT)
    eg.reset_all()
    check("بستن بازی‌های دیگر خون‌آشام را نبست", vp.is_active(CHAT))
    check("بازیکنان خون‌آشام دست‌نخورده ماندند", vp.player_count(CHAT) == 4)

    vp.reset_all(CHAT)
    check("ریست خون‌آشام کامل انجام شد", not vp.is_active(CHAT))
    router.reset_all()


def test_logging_covers_every_stage():
    print("\n### 📝 پوشش لاگ در تمام مراحل")

    async def scenario():
        router.reset_all()
        bot, event = Bot(), Event()
        await send(bot, event, 1, "خون آشام")
        for uid in range(41, 41 + vp.MAX_PLAYERS):
            await send(bot, event, uid, "شرکت")
        await asyncio.sleep(0.6)
        return bot

    bot = asyncio.run(scenario())
    for stage in ("FOX VAMPIRE START", "FOX VAMPIRE JOIN",
                  "FOX VAMPIRE JOIN CLOSED", "FOX VAMPIRE CHOSEN",
                  "ROLE DM TRY", "ROLE DM SENT", "GUESSING OPEN"):
        check(f"لاگ مرحلهٔ «{stage}» ثبت شد", bot.logger.has(stage))
    router.reset_all()


def main():
    test_bare_int_cannot_resolve()
    test_join_stores_peer()
    test_dm_succeeds_with_cold_cache()
    test_old_behaviour_would_fail()
    test_dm_failure_never_cancels_game()
    test_secret_fallback_hides_the_name()
    test_secret_fallback_entities_are_real()
    test_dm_preferred_when_available()
    test_deliver_role_modes()
    test_guessing_works_after_fallback()
    test_no_guessing_before_dm()
    test_group_messages_exact()
    test_full_flow_messages()
    test_rules()
    test_restart_blocked()
    test_random_selection()
    test_timeout_reveals()
    test_state_cleanup()
    test_repeated_games()
    test_isolation_from_other_games()
    test_logging_covers_every_stage()

    print("\n" + "=" * 52)
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
