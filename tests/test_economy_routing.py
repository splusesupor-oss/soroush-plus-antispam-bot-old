"""🔌 اتصال واقعی اقتصاد به سیستم فرمان ربات.

این تست از *همان* هندلری استفاده می‌کند که در زمان اجرا ثبت می‌شود:
``new_message_handler`` که داخل ``SoroushAntiSpamBot.run()`` تعریف و با
``@client.on(events.NewMessage())`` رجیستر می‌گردد.

چرا این تست لازم است: تست‌های قبلی مستقیماً ``handle_new_message`` را صدا
می‌زدند و کل مسیر core (گیت فعال بودن گروه، مسیر پیوی، گیت broadcast) را
دور می‌زدند. بنابراین اگر route در core شکسته بود، هیچ تستی آن را
نمی‌گرفت.

    python tests/test_economy_routing.py
"""
import asyncio
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import economy
import economy.shop.store as store
import economy.storage as storage
import handlers.economy_handler as eco_handler
import modules.group_storage as group_storage

PASSED = FAILED = 0
CHAT = -1009999888877
OTHER_CHAT = -100555444333


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


# ---------------------------------------------------------------------------
# ساخت ربات و گرفتن هندلر واقعی
# ---------------------------------------------------------------------------
class FakeClient:
    """کلاینتی که فقط هندلرها را ثبت می‌کند و شبکه ندارد."""

    def __init__(self, captured):
        self.captured = captured
        self.me = types.SimpleNamespace(id=555, username="aifox")
        self.sent = []

    def on(self, event):
        def decorator(fn):
            self.captured.append(fn)
            return fn
        return decorator

    async def connect(self):
        return None

    async def get_me(self):
        return self.me

    async def send_message(self, target, text, **kwargs):
        self.sent.append((target, text))
        return True

    async def run_until_disconnected(self):
        raise SystemExit

    def add_event_handler(self, *args, **kwargs):
        return None


class Logger:
    def __init__(self):
        self.info, self.errors = [], []

    def log_info(self, message):
        self.info.append(message)

    def log_error(self, message):
        self.errors.append(message)

    def has(self, needle):
        return any(needle in m for m in self.info + self.errors)


class ConfigManager:
    def get(self, key, default=None):
        return default


class Tracker:
    def get_count(self, *args):
        return 0

    def get_all_counts(self):
        return {}


class Detector:
    """آشکارساز اسپم خنثی: هیچ پیامی را اسپم نمی‌داند."""

    def is_spam(self, *args, **kwargs):
        return False, None

    def check_message(self, *args, **kwargs):
        return False, None


class Chat:
    def __init__(self, chat_id=CHAT, title="گروه تست"):
        self.id = chat_id
        self.title = title


class Message:
    _next = 1000

    def __init__(self, text):
        Message._next += 1
        self.message = text
        self.id = Message._next
        self.entities = None
        self.file = None


class User:
    def __init__(self, uid, name="علی", username=None):
        self.id = uid
        self.first_name = name
        self.last_name = None
        self.username = username


class Event:
    """رویداد پیام گروهی، مثل چیزی که splusthon می‌سازد."""

    def __init__(self, text, user_id, chat_id=CHAT, reply_target=None):
        self.message = Message(text)
        self.chat_id = chat_id
        self.is_private = False
        self.out = False
        self.replies = []
        self._user = User(user_id)
        self._chat_id = chat_id
        self.reply_to = reply_target is not None
        self._reply_target = reply_target

    async def get_chat(self):
        return Chat(self._chat_id)

    async def get_sender(self):
        return self._user

    async def reply(self, text, **kwargs):
        self.replies.append(text)
        return None

    async def respond(self, text, **kwargs):
        self.replies.append(text)
        return None

    async def get_reply_message(self):
        if self._reply_target is None:
            return None
        return _ReplyMessage(self._reply_target)

    def said(self, needle):
        return any(needle in m for m in self.replies)


class _ReplyMessage:
    def __init__(self, user):
        self._user = user

    async def get_sender(self):
        return self._user


async def build_handler():
    """ربات را بدون شبکه بالا می‌آورد و هندلر واقعی پیام را برمی‌گرداند."""
    import core.bot_working_split_ok as core

    captured = []
    bot = core.SoroushAntiSpamBot.__new__(core.SoroushAntiSpamBot)
    bot.client = FakeClient(captured)
    bot.logger = Logger()
    bot.config_manager = ConfigManager()
    bot.tracker = Tracker()
    bot.group_timer_tasks = {}
    bot.bot_account_id = 555
    bot.punished_users = set()
    bot.spam_burst_messages = {}
    bot.spammer_messages = {}
    bot.spam_burst_users = set()
    bot.detector = Detector()

    async def _noop(*args, **kwargs):
        return None

    bot.initialize_client = _noop

    try:
        await asyncio.wait_for(bot.run(), timeout=3)
    except (SystemExit, asyncio.TimeoutError):
        pass
    except Exception:
        pass

    handlers = [fn for fn in captured
                if getattr(fn, "__name__", "") == "new_message_handler"]
    return bot, (handlers[0] if handlers else None)


def fresh():
    temp = Path(tempfile.mkdtemp())
    storage.use_file(temp / "economy.json")
    store.ITEMS_FILE = temp / "shop.json"
    store._cache = None
    store._cache_mtime = None
    eco_handler.reset_all()
    group_storage.activate_group(CHAT, "گروه تست")
    return temp


# ===========================================================================
# ثبت شدن route
# ===========================================================================
def test_handler_is_registered():
    print("\n### 🔌 هندلر پیام واقعاً ثبت می‌شود")
    bot, handler = asyncio.run(build_handler())
    check("new_message_handler ثبت شد", handler is not None)
    check("هندلر async است",
          handler is not None and asyncio.iscoroutinefunction(handler))


def test_balance_command_routed():
    print("\n### 🔌 «موجودی» از مسیر واقعی فرمان")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        event = Event("موجودی", 777)
        await handler(event)
        return bot, event

    bot, event = asyncio.run(scenario())
    check("ربات پاسخ داد", bool(event.replies),
          "*** هیچ پاسخی نیامد ***")
    check("منوی کیف پول باز شد", event.said("کیف پول شما"))
    check("برنز نمایش داده شد", event.said("🥉 برنز:"))
    check("نقره نمایش داده شد", event.said("🥈 نقره:"))
    check("طلا نمایش داده شد", event.said("🥇 طلا:"))
    check("ارزش کل نمایش داده شد", event.said("ارزش کل"))
    check("همهٔ گزینه‌ها در همین منو هستند",
          all(event.said(x) for x in
              ("تبدیل برنز به نقره", "تبدیل نقره به طلا", "انتقال برنز",
               "انتقال نقره", "انتقال طلا", "تاریخچه", "جایزه روزانه")))
    check("route در لاگ ثبت شد", bot.logger.has("ECONOMY BALANCE MENU"))


def test_shop_command_routed():
    print("\n### 🔌 «فروشگاه» از مسیر واقعی فرمان")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        event = Event("فروشگاه", 777)
        await handler(event)
        return bot, event

    bot, event = asyncio.run(scenario())
    check("ربات پاسخ داد", bool(event.replies),
          "*** هیچ پاسخی نیامد ***")
    check("منوی فروشگاه باز شد", event.said("🛒 فروشگاه"))
    check("گزینهٔ لیست آیتم‌ها هست", event.said("لیست آیتم‌ها"))
    check("گزینهٔ خرید هست", event.said("خرید"))
    check("route در لاگ ثبت شد", bot.logger.has("ECONOMY SHOP MENU"))


# ===========================================================================
# عملیات واقعی روی دیتابیس
# ===========================================================================
def test_conversion_writes_to_database():
    print("\n### 💾 تبدیل واقعاً روی دیتابیس می‌نشیند")
    fresh()
    economy.add_bronze(777, 250)
    economy.add_silver(777, 100)
    before = economy.get_balance(777)

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("موجودی", 777))
        first = Event("1", 777)
        await handler(first)
        second = Event("2", 777)
        await handler(second)
        return first, second

    first, second = asyncio.run(scenario())
    check("تبدیل برنز پاسخ داد", first.said("تبدیل شد"))
    check("تبدیل نقره پاسخ داد", second.said("تبدیل شد"))

    after = economy.get_balance(777)
    check("برنز واقعاً کم شد",
          after[economy.BRONZE] == before[economy.BRONZE] - 100,
          f"-> {after[economy.BRONZE]}")
    check("طلا واقعاً اضافه شد", after[economy.GOLD] == 10,
          f"-> {after[economy.GOLD]}")

    # اثبات نوشته شدن روی دیسک، نه فقط حافظه
    raw = json.loads(storage.DATA_FILE.read_text(encoding="utf-8"))
    stored = raw["users"]["777"]
    check("مقدار روی دیسک ذخیره شد",
          stored["gold"] == 10 and stored["bronze"] == 150,
          f"-> {stored['gold']}/{stored['bronze']}")
    check("ارزش کل روی دیسک بازمحاسبه شد",
          stored["total_coin_value"] == after["total_coin_value"])
    check("تراکنش‌ها روی دیسک ثبت شدند",
          len(stored["transactions"]) >= 2)


def test_daily_and_history_from_menu():
    print("\n### 💾 جایزه روزانه و تاریخچه از داخل منو")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("موجودی", 777))
        daily = Event("7", 777)
        await handler(daily)
        again = Event("7", 777)
        await handler(again)
        history = Event("6", 777)
        await handler(history)
        return daily, again, history

    daily, again, history = asyncio.run(scenario())
    check("جایزه روزانه پرداخت شد", daily.said("جایزه روزانه دریافت شد"))
    check("موجودی واقعاً بالا رفت",
          economy.get_balance(777)[economy.BRONZE] == 25,
          f"-> {economy.get_balance(777)[economy.BRONZE]}")
    check("دریافت دوباره رد شد", again.said("قبلاً دریافت"))
    check("موجودی دوباره اضافه نشد",
          economy.get_balance(777)[economy.BRONZE] == 25)
    check("تاریخچه نمایش داده شد", history.said("تاریخچه تراکنش"))
    check("تراکنش در دیتابیس هست",
          len(economy.transaction_history(777)) == 1)


def test_transfer_from_menu_writes_db():
    print("\n### 💾 انتقال از داخل منو روی دیتابیس")
    fresh()
    economy.add_bronze(777, 100)
    target = User(888, "حسین")

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("موجودی", 777))
        prompt = Event("3", 777)
        await handler(prompt)
        amount = Event("40", 777, reply_target=target)
        await handler(amount)
        return prompt, amount

    prompt, amount = asyncio.run(scenario())
    check("راهنمای انتقال آمد", prompt.said("انتقال برنز"))
    check("انتقال انجام شد", amount.said("منتقل شد"))
    check("از فرستنده واقعاً کم شد",
          economy.get_balance(777)[economy.BRONZE] == 60,
          f"-> {economy.get_balance(777)[economy.BRONZE]}")
    check("به گیرنده واقعاً رسید",
          economy.get_balance(888)[economy.BRONZE] == 40,
          f"-> {economy.get_balance(888)[economy.BRONZE]}")

    raw = json.loads(storage.DATA_FILE.read_text(encoding="utf-8"))
    check("هر دو طرف روی دیسک ذخیره شدند",
          raw["users"]["777"]["bronze"] == 60
          and raw["users"]["888"]["bronze"] == 40)


def test_shop_buy_from_menu_writes_db():
    print("\n### 💾 خرید از فروشگاه روی دیتابیس")
    fresh()
    economy.shop.add_item("badge", "نشان طلایی", 50, "bronze", stock=1)
    economy.add_bronze(777, 120)

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("فروشگاه", 777))
        listing = Event("1", 777)
        await handler(listing)
        prompt = Event("2", 777)
        await handler(prompt)
        buy = Event("badge", 777)
        await handler(buy)
        return listing, prompt, buy

    listing, prompt, buy = asyncio.run(scenario())
    check("آیتم در فهرست دیده شد", listing.said("نشان طلایی"))
    check("راهنمای خرید آمد", prompt.said("شناسهٔ آیتم"))
    check("خرید انجام شد", buy.said("خریداری شد"))
    check("سکه واقعاً کسر شد",
          economy.get_balance(777)[economy.BRONZE] == 70,
          f"-> {economy.get_balance(777)[economy.BRONZE]}")

    raw = json.loads(storage.DATA_FILE.read_text(encoding="utf-8"))
    check("خرید روی دیسک ثبت شد",
          len(raw["users"]["777"].get("purchases", [])) == 1)
    check("تراکنش خرید ثبت شد",
          economy.transaction_history(777)[0]["kind"] == "purchase")


def test_game_reward_reaches_economy_via_real_route():
    print("\n### 💾 جایزهٔ بازی از مسیر واقعی به اقتصاد می‌رسد")
    fresh()
    import modules.emoji_guess as eg
    eg.reset_all()

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("حدس ایموجی", 777))
        puzzle = eg._ACTIVE.get(CHAT)
        if puzzle is None:
            return None
        answer = Event(puzzle["answer"], 777)
        await handler(answer)
        return answer

    answer = asyncio.run(scenario())
    check("بازی از مسیر واقعی شروع شد", answer is not None)
    if answer is not None:
        check("پاسخ درست پذیرفته شد", answer.said("پاسخ صحیح"))
        balance = economy.get_balance(777)
        check("جایزه در اقتصاد ثبت شد",
              balance[economy.BRONZE] == eg.REWARD_BRONZE,
              f"-> {balance[economy.BRONZE]}")
        raw = json.loads(storage.DATA_FILE.read_text(encoding="utf-8"))
        check("جایزه روی دیسک ذخیره شد",
              raw["users"]["777"]["bronze"] == eg.REWARD_BRONZE)
    eg.reset_all()


# ===========================================================================
# رفتار درست در گروه غیرفعال
# ===========================================================================
def test_inactive_group_blocks():
    print("\n### 🚫 گروه غیرفعال: هیچ پاسخی داده نمی‌شود")
    fresh()
    group_storage.deactivate_group(CHAT, "گروه تست")

    async def scenario():
        bot, handler = await build_handler()
        event = Event("موجودی", 777)
        await handler(event)
        return event

    event = asyncio.run(scenario())
    check("در گروه غیرفعال پاسخی نمی‌آید", not event.replies,
          f"-> {event.replies}")
    group_storage.activate_group(CHAT, "گروه تست")


def test_unregistered_group_blocks():
    print("\n### 🚫 گروه ثبت‌نشده: هیچ پاسخی داده نمی‌شود")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        event = Event("موجودی", 777, chat_id=OTHER_CHAT)
        await handler(event)
        return event

    event = asyncio.run(scenario())
    check("در گروه ثبت‌نشده پاسخی نمی‌آید", not event.replies,
          f"-> {event.replies}")


def test_unrelated_text_passes_through():
    print("\n### 🔒 متن نامرتبط منو را خراب نمی‌کند")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("موجودی", 777))
        junk = Event("سلام بچه‌ها", 777)
        await handler(junk)
        menu = Event("موجودی", 777)
        await handler(menu)
        return junk, menu

    junk, menu = asyncio.run(scenario())
    check("پیام نامرتبط پاسخ اقتصادی نمی‌گیرد",
          not junk.said("کیف پول"), f"-> {junk.replies}")
    check("منو هنوز کار می‌کند", menu.said("کیف پول شما"))


# ===========================================================================
# لاگ تشخیصی و مقاومت در برابر خطا
# ===========================================================================
def test_diagnostic_logging():
    """مسیر کامل باید قابل ردیابی باشد: ورود، خواندن، رندر، ارسال."""
    print("\n### 🩺 لاگ تشخیصی کامل")
    fresh()
    economy.add_bronze(777, 152)
    economy.add_silver(777, 34)
    economy.add_gold(777, 8)

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("موجودی", 777))
        return bot

    bot = asyncio.run(scenario())
    for stage in ("ECONOMY HANDLER ENTER", "ECONOMY BALANCE READ",
                  "ECONOMY BALANCE RENDERED", "ECONOMY BALANCE MENU SENT"):
        check(f"لاگ «{stage}» ثبت شد", bot.logger.has(stage))

    read = [m for m in bot.logger.info if "ECONOMY BALANCE READ" in m]
    check("مقدار واقعی موجودی لاگ شد",
          read and "bronze=152" in read[0] and "gold=8" in read[0],
          f"-> {read[:1]}")
    check("ارزش کل لاگ شد",
          read and "total_coin_value=1292" in read[0])
    check("مسیر فایل دیتابیس لاگ شد",
          read and "db_file=" in read[0])


def test_shop_diagnostic_logging():
    print("\n### 🩺 لاگ تشخیصی فروشگاه")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        await handler(Event("فروشگاه", 777))
        return bot

    bot = asyncio.run(scenario())
    check("لاگ ورود ثبت شد", bot.logger.has("ECONOMY HANDLER ENTER"))
    check("لاگ خواندن فروشگاه ثبت شد", bot.logger.has("ECONOMY SHOP READ"))
    check("لاگ ارسال ثبت شد", bot.logger.has("ECONOMY SHOP MENU SENT"))


def test_entity_rejection_falls_back_to_plain():
    """اگر سرور entity را نپذیرد، متن ساده فرستاده می‌شود، نه هیچ."""
    print("\n### 🛡️ پاسخ حتی وقتی سرور entity را رد کند")
    fresh()
    economy.add_bronze(777, 152)

    class RejectingEvent(Event):
        async def reply(self, text, **kwargs):
            if kwargs.get("formatting_entities"):
                raise ValueError("ENTITY_BOUNDS_INVALID")
            self.replies.append(text)

    async def scenario():
        bot, handler = await build_handler()
        event = RejectingEvent("موجودی", 777)
        await handler(event)
        return bot, event

    bot, event = asyncio.run(scenario())
    check("کاربر همچنان پاسخ می‌گیرد", bool(event.replies),
          "*** هیچ خروجی نیامد ***")
    check("متن کامل منو ارسال شد",
          event.said("کیف پول شما") and event.said("۱۵۲"))
    check("بازگشت به متن ساده لاگ شد",
          bot.logger.has("retrying plain"))


def test_unexpected_error_is_reported():
    """هر خطای غیرمنتظره باید هم لاگ شود هم به کاربر گفته شود."""
    print("\n### 🛡️ خطای غیرمنتظره بی‌صدا نمی‌ماند")
    fresh()
    import economy.ui.balance_menu as bm
    original = bm.render_menu

    def boom(user_id):
        raise RuntimeError("db unavailable")

    bm.render_menu = boom
    try:
        async def scenario():
            bot, handler = await build_handler()
            event = Event("موجودی", 777)
            await handler(event)
            return bot, event

        bot, event = asyncio.run(scenario())
        check("خطا در لاگ ثبت شد",
              bot.logger.has("ECONOMY BALANCE MENU FAILED"))
        check("traceback ثبت شد", bot.logger.has("Traceback"))
        check("به کاربر اطلاع داده شد", event.said("خطا در نمایش موجودی"))
    finally:
        bm.render_menu = original


def test_repeated_command_not_swallowed():
    """ارسال پیاپی «موجودی» نباید توسط ضداسپم بلعیده شود."""
    print("\n### 🔁 ارسال پیاپی دستور")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        results = []
        for _ in range(5):
            event = Event("موجودی", 777)
            await handler(event)
            results.append(bool(event.replies))
        return results

    results = asyncio.run(scenario())
    check("هر ۵ بار پاسخ داده شد", all(results), f"-> {results}")


def test_owner_outgoing_message_works():
    """در userbot، پیام خود مالک event.out=True دارد."""
    print("\n### 👤 پیام خروجی مالک در حالت userbot")
    fresh()
    import modules.owner_check as oc
    owner_id = oc.get_owner()["user_id"]

    async def scenario():
        bot, handler = await build_handler()
        event = Event("موجودی", owner_id)
        event.out = True
        event._user = User(owner_id, "osine1", username="osine1")
        await handler(event)
        return event

    event = asyncio.run(scenario())
    check("پیام خروجی مالک هم پاسخ می‌گیرد", bool(event.replies),
          "*** هیچ خروجی نیامد ***")
    check("منو باز شد", event.said("کیف پول شما"))


# ===========================================================================
# پیوی — مسیری که قبلاً کاملاً دور ریخته می‌شد
# ===========================================================================
class PrivateEvent(Event):
    """پیام خصوصی: is_private=True و peer یک کاربر است، نه گروه."""

    def __init__(self, text, user_id, reply_target=None):
        super().__init__(text, user_id, chat_id=user_id,
                         reply_target=reply_target)
        self.is_private = True

    async def get_chat(self):
        return User(self._chat_id)


def test_private_balance_command():
    """گارد رگرسیون: شاخهٔ پیوی با یک return بی‌قیدوشرط تمام می‌شد."""
    print("\n### 📩 «موجودی» در پیوی")
    fresh()
    economy.add_bronze(777, 152)
    economy.add_silver(777, 34)
    economy.add_gold(777, 8)

    async def scenario():
        bot, handler = await build_handler()
        event = PrivateEvent("موجودی", 777)
        await handler(event)
        return bot, event

    bot, event = asyncio.run(scenario())
    check("در پیوی پاسخ داده می‌شود", bool(event.replies),
          "*** هیچ خروجی نیامد ***")
    check("منوی کیف پول باز شد", event.said("کیف پول شما"))
    check("موجودی واقعی نمایش داده شد", event.said("۱۵۲"))
    check("route پیوی لاگ شد", bot.logger.has("ECONOMY BALANCE READ"))


def test_private_shop_command():
    print("\n### 📩 «فروشگاه» در پیوی")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        event = PrivateEvent("فروشگاه", 777)
        await handler(event)
        return event

    event = asyncio.run(scenario())
    check("در پیوی پاسخ داده می‌شود", bool(event.replies),
          "*** هیچ خروجی نیامد ***")
    check("منوی فروشگاه باز شد", event.said("🛒 فروشگاه"))
    check("گزینه‌ها نمایش داده شدند",
          event.said("لیست آیتم‌ها") and event.said("خرید"))


def test_private_menu_options_work():
    print("\n### 📩 گزینه‌های منو در پیوی روی دیتابیس")
    fresh()
    economy.add_bronze(777, 250)
    economy.add_silver(777, 100)

    async def scenario():
        bot, handler = await build_handler()
        await handler(PrivateEvent("موجودی", 777))
        first = PrivateEvent("1", 777)
        await handler(first)
        second = PrivateEvent("2", 777)
        await handler(second)
        daily = PrivateEvent("7", 777)
        await handler(daily)
        return first, second, daily

    first, second, daily = asyncio.run(scenario())
    check("تبدیل برنز در پیوی کار کرد", first.said("تبدیل شد"))
    check("تبدیل نقره در پیوی کار کرد", second.said("تبدیل شد"))
    check("جایزه روزانه در پیوی کار کرد",
          daily.said("جایزه روزانه دریافت شد"))

    balance = economy.get_balance(777)
    check("برنز واقعاً تغییر کرد", balance[economy.BRONZE] == 175,
          f"-> {balance[economy.BRONZE]}")
    check("طلا واقعاً ساخته شد", balance[economy.GOLD] == 10,
          f"-> {balance[economy.GOLD]}")

    raw = json.loads(storage.DATA_FILE.read_text(encoding="utf-8"))
    check("همه چیز روی دیسک ذخیره شد",
          raw["users"]["777"]["gold"] == 10
          and len(raw["users"]["777"]["transactions"]) >= 3)


def test_private_shop_buy():
    print("\n### 📩 خرید از فروشگاه در پیوی")
    fresh()
    economy.shop.add_item("badge", "نشان", 50, "bronze")
    economy.add_bronze(777, 100)

    async def scenario():
        bot, handler = await build_handler()
        await handler(PrivateEvent("فروشگاه", 777))
        prompt = PrivateEvent("2", 777)
        await handler(prompt)
        buy = PrivateEvent("badge", 777)
        await handler(buy)
        return prompt, buy

    prompt, buy = asyncio.run(scenario())
    check("راهنمای خرید آمد", prompt.said("شناسهٔ آیتم"))
    check("خرید انجام شد", buy.said("خریداری شد"))
    check("سکه واقعاً کسر شد",
          economy.get_balance(777)[economy.BRONZE] == 50,
          f"-> {economy.get_balance(777)[economy.BRONZE]}")


def test_private_unrelated_text_ignored():
    print("\n### 📩 متن نامرتبط در پیوی")
    fresh()

    async def scenario():
        bot, handler = await build_handler()
        event = PrivateEvent("سلام", 777)
        await handler(event)
        return event

    event = asyncio.run(scenario())
    check("متن نامرتبط پاسخ اقتصادی نمی‌گیرد",
          not event.said("کیف پول"), f"-> {event.replies}")


def main():
    test_handler_is_registered()
    test_balance_command_routed()
    test_shop_command_routed()
    test_conversion_writes_to_database()
    test_daily_and_history_from_menu()
    test_transfer_from_menu_writes_db()
    test_shop_buy_from_menu_writes_db()
    test_game_reward_reaches_economy_via_real_route()
    test_inactive_group_blocks()
    test_unregistered_group_blocks()
    test_unrelated_text_passes_through()
    test_diagnostic_logging()
    test_shop_diagnostic_logging()
    test_entity_rejection_falls_back_to_plain()
    test_unexpected_error_is_reported()
    test_repeated_command_not_swallowed()
    test_owner_outgoing_message_works()
    test_private_balance_command()
    test_private_shop_command()
    test_private_menu_options_work()
    test_private_shop_buy()
    test_private_unrelated_text_ignored()

    print("\n" + "=" * 52)
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
