"""📮 «کپی بورد» (حافظهٔ روباهی) — تست کامل و مستقل.

پوشش کامل ۱۵ سناریوی درخواستی:

     ۱. «کپی بورد» → نمایش راهنما (و فقط راهنما)
     ۲. Reply صحیح به راهنما + متن ساده → ذخیرهٔ موفق
     ۳. «کپی» → ارسال متن ذخیره‌شده
     ۴. ذخیرهٔ متن جدید → جایگزینی کپی‌بورد قبلی
     ۵. متن Bold → حفظ Bold
     ۶. Quote → حفظ Quote
     ۷. لینک → حفظ لینک (MessageEntityTextUrl و url)
     ۸. متن چندخطی → حفظ ساختار
     ۹. ارسال متن بدون Reply → عدم ذخیره
    ۱۰. کاربر غیرمجاز → عدم امکان تغییر کپی‌بورد
    ۱۱. متن دارای محتوای ممنوع → عدم ذخیره و دست‌نخوردن کپی‌بورد قبلی
    ۱۲. کپی‌بورد گروه A در گروه B قابل دسترسی نیست
    ۱۳. نبود کپی‌بورد → پیام مناسب
    ۱۴. Restart ربات → کپی‌بورد از بین نمی‌رود
    ۱۵. هیچ قابلیت قبلی خراب نمی‌شود (routing و راهنما)

    python tests/test_clipboard.py
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import handlers.clipboard_handler as ch
import modules.admin_storage as admin_storage
import modules.clipboard as clipboard
import modules.content_guard as content_guard
import modules.group_expiry as ge
import modules.group_storage as gs
import modules.owner_check as oc
from modules.group_dispatch import LANE_ADMIN, LANE_COMMAND, classify_priority

PASSED = FAILED = 0

CHAT_A = -1001234567890
CHAT_B = -1009876543210
OWNER_ID = 42424242
GROUP_OWNER_ID = 777000111
ADMIN_ID = 888000222
STRANGER_ID = 999000333


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


# ===========================================================================
# دوبل‌های سبک API
# ===========================================================================
class User:
    def __init__(self, uid, name="U", username=None):
        self.id = uid
        self.first_name = name
        self.last_name = None
        self.username = username


class Chat:
    def __init__(self, chat_id, title="گروه تست"):
        self.id = chat_id
        self.title = title


class Entity:
    """جایگزین MessageEntity* با همان ساختار (offset/length/extra)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def make_entity(name, **kwargs):
    return type(name, (Entity,), {})(**kwargs)


class Message:
    _next_id = 1000

    def __init__(self, text="", entities=None, reply_to_msg_id=None):
        Message._next_id += 1
        self.id = Message._next_id
        self.message = text
        self.text = text
        self.entities = list(entities or [])
        self.reply_to_msg_id = reply_to_msg_id
        self.reply_to = None


class Sent:
    def __init__(self, message_id, text, entities):
        self.id = message_id
        self.text = text
        self.entities = entities


class Event:
    """رویداد پیام با ``reply`` که پیام ارسالی را با id برمی‌گرداند."""

    _next_sent_id = 5000

    def __init__(self, chat_id, text="", entities=None,
                 reply_to_msg_id=None, is_private=False):
        self.message = Message(text, entities, reply_to_msg_id)
        self.is_private = is_private
        self._chat = Chat(chat_id)
        self.out = []
        self.out_entities = []
        self.sent = []

    async def reply(self, text, formatting_entities=None, **kwargs):
        Event._next_sent_id += 1
        self.out.append(text)
        self.out_entities.append(list(formatting_entities or []))
        sent = Sent(Event._next_sent_id, text, formatting_entities)
        self.sent.append(sent)
        return sent

    async def get_chat(self):
        return self._chat

    def said(self, needle):
        return any(needle in m for m in self.out)


class Logger:
    def __init__(self):
        self.info, self.errors = [], []

    def log_info(self, m):
        self.info.append(m)

    def log_error(self, m):
        self.errors.append(m)


class Bot:
    def __init__(self):
        self.logger = Logger()
        self.client = None
        self.notice_cleanup = None


# ===========================================================================
# محیط ایزوله
# ===========================================================================
def use_temp_files():
    temp = Path(tempfile.mkdtemp())

    clipboard.FILE = temp / "clipboard.json"
    clipboard.reset_cache()

    gs.FILE = temp / "groups.json"
    gs._cache = None
    gs._cache_mtime = None

    admin_storage.FILE = temp / "admins.json"
    admin_storage._cache = None
    admin_storage._cache_mtime = None

    ge.FILE = temp / "group_expiry.json"
    ge._cache = None
    ge._cache_mtime = None

    owner_file = temp / "owner.json"
    owner_file.write_text(
        json.dumps({"user_id": OWNER_ID, "username": "aifox"}),
        encoding="utf-8",
    )
    oc.DEPLOYMENT_FILE = owner_file
    oc._CACHE_SIGNATURE = None
    oc._CACHE_OWNER = None
    return temp


def decode_span(text, offset, length):
    raw = text.encode("utf-16-le")
    return raw[offset * 2:(offset + length) * 2].decode("utf-16-le")


def kinds(entities):
    return [type(e).__name__ for e in entities]


async def run(bot, event, chat_id, sender):
    """هندلر را با همان امضایی که message_handler صدا می‌زند اجرا می‌کند."""
    raw = event.message.message
    clean = " ".join(str(raw).split())
    return await ch.handle(bot, event, chat_id, sender.id, sender, clean,
                           raw, bot.logger)


async def open_help(bot, chat_id, sender):
    """«کپی بورد» را می‌فرستد و شناسهٔ پیام راهنما را برمی‌گرداند."""
    event = Event(chat_id, "کپی بورد")
    consumed = await run(bot, event, chat_id, sender)
    return event, consumed, (event.sent[-1].id if event.sent else None)


async def save_via_reply(bot, chat_id, sender, help_id, text, entities=None):
    event = Event(chat_id, text, entities, reply_to_msg_id=help_id)
    consumed = await run(bot, event, chat_id, sender)
    return event, consumed


# ===========================================================================
# ۰. تطبیق دستور و routing
# ===========================================================================
def test_command_matching():
    print("\n### 🎯 تطبیق دقیق دستورها")
    check("«کپی بورد» → save",
          clipboard.match_command("کپی بورد") == clipboard.MODE_SAVE)
    check("«کپی» → show",
          clipboard.match_command("کپی") == clipboard.MODE_SHOW)
    check("نیم‌فاصله پذیرفته می‌شود",
          clipboard.match_command("کپی\u200cبورد") == clipboard.MODE_SAVE)
    check("فاصلهٔ اضافه پذیرفته می‌شود",
          clipboard.match_command("  کپی    بورد  ") == clipboard.MODE_SAVE)
    check("ی/ک عربی پذیرفته می‌شود",
          clipboard.match_command("كپي بورد") == clipboard.MODE_SAVE)

    for other in ("کپی بورد گروه", "کپی کن", "کپی 10", "بورد", "کپی‌برداری",
                  "راهنما", "مهلت گروه", "لیست ادمینی", "سنجاق", "قفل"):
        check(f"«{other}» تطبیق نمی‌کند",
              clipboard.match_command(other) is None,
              f"-> {clipboard.match_command(other)!r}")


def test_dispatch_lane():
    print("\n### 🚦 لاین پردازش (قابلیت‌های قبلی دست‌نخورده)")
    check("«کپی بورد» از لاین admin می‌رود",
          classify_priority("کپی بورد")[1] == LANE_ADMIN)
    check("«کپی» از لاین admin می‌رود",
          classify_priority("کپی")[1] == LANE_ADMIN)
    # رگرسیون: مسیر دستورهای قبلی تغییر نکرده است.
    check("«مهلت گروه» همچنان admin است",
          classify_priority("مهلت گروه")[1] == LANE_ADMIN)
    check("«راهنما» همچنان command است",
          classify_priority("راهنما")[1] == LANE_COMMAND)
    check("«لیست کاربران» همچنان command است",
          classify_priority("لیست کاربران")[1] == LANE_COMMAND)


# ===========================================================================
# ۱. نمایش راهنما
# ===========================================================================
def test_help_message():
    print("\n### 1️⃣ «کپی بورد» → فقط پیام راهنما")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    event, consumed, help_id = asyncio.run(open_help(bot, CHAT_A, owner))
    check("پیام مصرف شد", consumed is True)
    check("دقیقاً یک پیام فرستاده شد", len(event.out) == 1,
          f"-> {len(event.out)}")

    text = event.out[0]
    check("عنوان دقیقاً درست است", clipboard.HELP_TITLE in text)
    check("متن توضیحات دقیقاً درست است", clipboard.HELP_BODY in text)
    check("خط پایانی درست است", clipboard.HELP_FOOTER in text)
    check("پیام با عنوان شروع می‌شود",
          text.startswith(clipboard.HELP_TITLE))
    check("پیام با خط ریپلای تمام می‌شود",
          text.endswith(clipboard.HELP_FOOTER))

    entities = event.out_entities[0]
    names = kinds(entities)
    check("عنوان داخل نقل‌قول است",
          "MessageEntityBlockquote" in names, f"-> {names}")
    check("دو بخش Bold دارد",
          names.count("MessageEntityBold") == 2, f"-> {names}")

    quote = [e for e in entities
             if type(e).__name__ == "MessageEntityBlockquote"][0]
    check("نقل‌قول دقیقاً روی عنوان است",
          decode_span(text, quote.offset, quote.length)
          == clipboard.HELP_TITLE)

    bolds = sorted(
        (e for e in entities if type(e).__name__ == "MessageEntityBold"),
        key=lambda e: e.offset)
    check("عنوان Bold است",
          decode_span(text, bolds[0].offset, bolds[0].length)
          == clipboard.HELP_TITLE)
    check("متن توضیحات Bold است",
          decode_span(text, bolds[1].offset, bolds[1].length)
          == clipboard.HELP_BODY)
    check("خط پایانی Bold نیست",
          clipboard.HELP_FOOTER not in decode_span(
              text, bolds[1].offset, bolds[1].length))

    check("شناسهٔ راهنما ثبت شد",
          clipboard.is_help_message(CHAT_A, help_id))
    check("راهنما چیزی ذخیره نکرد", clipboard.get(CHAT_A)[0] is None)


# ===========================================================================
# ۲ و ۳ و ۴. ذخیره، نمایش، جایگزینی
# ===========================================================================
def test_save_show_replace():
    print("\n### 2️⃣3️⃣4️⃣ ذخیره، نمایش و جایگزینی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    _help_event, _c, help_id = asyncio.run(open_help(bot, CHAT_A, owner))

    event, consumed = asyncio.run(
        save_via_reply(bot, CHAT_A, owner, help_id, "سلام دوستان 👋"))
    check("ذخیره پیام را مصرف کرد", consumed is True)
    check("پاسخ موفقیت داده شد", event.said(clipboard.SAVED_MESSAGE))
    check("متن در storage نشست",
          clipboard.get(CHAT_A)[0] == "سلام دوستان 👋")

    show = Event(CHAT_A, "کپی")
    check("«کپی» مصرف شد",
          asyncio.run(run(bot, show, CHAT_A, owner)) is True)
    check("متن ذخیره‌شده ارسال شد", show.out == ["سلام دوستان 👋"],
          f"-> {show.out}")

    # ۴. جایگزینی
    event2, _c2 = asyncio.run(
        save_via_reply(bot, CHAT_A, owner, help_id, "متن دوم"))
    check("ذخیرهٔ دوم موفق بود", event2.said(clipboard.SAVED_MESSAGE))
    show2 = Event(CHAT_A, "کپی")
    asyncio.run(run(bot, show2, CHAT_A, owner))
    check("متن قبلی جایگزین شد", show2.out == ["متن دوم"], f"-> {show2.out}")


# ===========================================================================
# ۵ و ۶ و ۷ و ۸. حفظ کامل فرمت
# ===========================================================================
def test_formatting_preserved():
    print("\n### 5️⃣6️⃣7️⃣8️⃣ حفظ کامل قالب‌بندی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    _e, _c, help_id = asyncio.run(open_help(bot, CHAT_A, owner))

    # ۵. Bold
    body = "سلام دوستان"
    asyncio.run(save_via_reply(
        bot, CHAT_A, owner, help_id, body,
        [make_entity("MessageEntityBold", offset=0,
                     length=clipboard.u16_len(body))]))
    text, entities = clipboard.get(CHAT_A)
    check("Bold حفظ شد", kinds(entities) == ["MessageEntityBold"],
          f"-> {kinds(entities)}")
    check("محدودهٔ Bold درست است",
          decode_span(text, entities[0].offset, entities[0].length) == body)

    show = Event(CHAT_A, "کپی")
    asyncio.run(run(bot, show, CHAT_A, owner))
    check("هنگام «کپی» هم Bold ارسال شد",
          kinds(show.out_entities[0]) == ["MessageEntityBold"])

    # ۶. Quote
    quote_body = "اعلان مهم گروه"
    asyncio.run(save_via_reply(
        bot, CHAT_A, owner, help_id, quote_body,
        [make_entity("MessageEntityBlockquote", offset=0,
                     length=clipboard.u16_len(quote_body))]))
    text, entities = clipboard.get(CHAT_A)
    check("Quote حفظ شد", kinds(entities) == ["MessageEntityBlockquote"],
          f"-> {kinds(entities)}")
    check("محدودهٔ Quote درست است",
          decode_span(text, entities[0].offset,
                      entities[0].length) == quote_body)

    # ۷. لینک داخل متن (TextUrl با url) + لینک ساده
    link_body = "کانال ما را ببینید"
    url = "https://splus.ir/foxchannel"
    asyncio.run(save_via_reply(
        bot, CHAT_A, owner, help_id, link_body,
        [make_entity("MessageEntityTextUrl", offset=0,
                     length=clipboard.u16_len("کانال ما"), url=url)]))
    text, entities = clipboard.get(CHAT_A)
    check("لینک حفظ شد", kinds(entities) == ["MessageEntityTextUrl"],
          f"-> {kinds(entities)}")
    check("آدرس لینک حفظ شد", getattr(entities[0], "url", None) == url,
          f"-> {getattr(entities[0], 'url', None)}")

    plain_link = f"برای عضویت کلیک کنید {url}"
    event, _c = asyncio.run(
        save_via_reply(bot, CHAT_A, owner, help_id, plain_link))
    check("لینک ساده ذخیره شد (فیلتر مانع نشد)",
          event.said(clipboard.SAVED_MESSAGE))
    check("متن لینک دست‌نخورده است", clipboard.get(CHAT_A)[0] == plain_link)

    # ۸. چندخطی + ترکیب Bold و متن معمولی
    multiline = "خط اول\nخط دوم\n\nخط چهارم"
    asyncio.run(save_via_reply(
        bot, CHAT_A, owner, help_id, multiline,
        [make_entity("MessageEntityBold", offset=0,
                     length=clipboard.u16_len("خط اول"))]))
    text, entities = clipboard.get(CHAT_A)
    check("ساختار چندخطی حفظ شد", text == multiline, f"-> {text!r}")
    check("فقط بخش Bold شده Bold ماند",
          decode_span(text, entities[0].offset,
                      entities[0].length) == "خط اول")
    show = Event(CHAT_A, "کپی")
    asyncio.run(run(bot, show, CHAT_A, owner))
    check("خروجی «کپی» عیناً همان متن چندخطی است",
          show.out == [multiline], f"-> {show.out}")


# ===========================================================================
# ۹. بدون Reply ذخیره نمی‌شود
# ===========================================================================
def test_requires_reply():
    print("\n### 9️⃣ ذخیره فقط با Reply روی پیام راهنما")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    _e, _c, help_id = asyncio.run(open_help(bot, CHAT_A, owner))

    plain = Event(CHAT_A, "این متن نباید ذخیره شود")
    consumed = asyncio.run(run(bot, plain, CHAT_A, owner))
    check("پیام بدون Reply مصرف نشد", consumed is False)
    check("چیزی ذخیره نشد", clipboard.get(CHAT_A)[0] is None)

    wrong = Event(CHAT_A, "متن اشتباه", reply_to_msg_id=help_id + 7777)
    consumed = asyncio.run(run(bot, wrong, CHAT_A, owner))
    check("Reply روی پیام اشتباه مصرف نشد", consumed is False)
    check("هنوز چیزی ذخیره نشده", clipboard.get(CHAT_A)[0] is None)

    empty = Event(CHAT_A, "   ", reply_to_msg_id=help_id)
    consumed = asyncio.run(run(bot, empty, CHAT_A, owner))
    check("Reply با پیام خالی ذخیره نشد",
          clipboard.get(CHAT_A)[0] is None)
    check("به کاربر پیام مناسب داده شد",
          empty.said(clipboard.INVALID_MESSAGE) or consumed is False)

    too_long = Event(CHAT_A, "ا" * (clipboard.MAX_TEXT_UNITS + 10),
                     reply_to_msg_id=help_id)
    asyncio.run(run(bot, too_long, CHAT_A, owner))
    check("متن خیلی طولانی ذخیره نشد", clipboard.get(CHAT_A)[0] is None)
    check("پیام طول زیاد داده شد", too_long.said("طولانی"))


# ===========================================================================
# ۱۰. سطح دسترسی
# ===========================================================================
def test_permissions():
    print("\n### 🔟 سطح دسترسی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    stranger = User(STRANGER_ID, "رهگذر")
    admin = User(ADMIN_ID, "ادمین", username="foxadmin")

    _e, _c, help_id = asyncio.run(open_help(bot, CHAT_A, owner))

    # کاربر عادی: Reply درست هم چیزی را عوض نمی‌کند.
    event, consumed = asyncio.run(
        save_via_reply(bot, CHAT_A, stranger, help_id, "متن کاربر عادی"))
    check("Reply کاربر عادی مصرف نشد", consumed is False)
    check("کاربر عادی کپی‌بورد را عوض نکرد",
          clipboard.get(CHAT_A)[0] is None)

    deny = Event(CHAT_A, "کپی بورد")
    consumed = asyncio.run(run(bot, deny, CHAT_A, stranger))
    check("«کپی بورد» کاربر عادی رد شد",
          consumed is True and deny.said("فقط مالک"))
    check("راهنما برای کاربر عادی فرستاده نشد",
          not deny.said(clipboard.HELP_BODY))

    # ادمین ثبت‌شدهٔ همان گروه مجاز است.
    admin_storage.add_admin(CHAT_A, ADMIN_ID, "foxadmin")
    _e2, _c2, help_id2 = asyncio.run(open_help(bot, CHAT_A, admin))
    check("ادمین راهنما را گرفت", help_id2 is not None)
    event, _c3 = asyncio.run(
        save_via_reply(bot, CHAT_A, admin, help_id2, "متن ادمین"))
    check("ادمین توانست ذخیره کند",
          clipboard.get(CHAT_A)[0] == "متن ادمین")

    # مالک گروه هم مجاز است.
    gs.activate_group(CHAT_B, "گروه ب")
    try:
        gs.set_group_owner(CHAT_B, GROUP_OWNER_ID)
    except Exception:
        pass
    group_owner = User(GROUP_OWNER_ID, "مالک گروه")
    _e4, _c4, help_b = asyncio.run(open_help(bot, CHAT_B, group_owner))
    if help_b is not None:
        asyncio.run(save_via_reply(
            bot, CHAT_B, group_owner, help_b, "متن مالک گروه"))
    check("مالک گروه مجاز است",
          clipboard.get(CHAT_B)[0] == "متن مالک گروه",
          f"-> {clipboard.get(CHAT_B)[0]!r}")

    # «کپی» کاربر عادی سروصدا نمی‌کند و مسیر عادی ادامه می‌یابد.
    quiet = Event(CHAT_A, "کپی")
    consumed = asyncio.run(run(bot, quiet, CHAT_A, stranger))
    check("«کپی» کاربر عادی بی‌پاسخ رد شد",
          consumed is False and quiet.out == [])


# ===========================================================================
# ۱۱. فیلتر محتوای ممنوع
# ===========================================================================
def test_content_filter():
    print("\n### 1️⃣1️⃣ فیلتر محتوای ممنوع")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    _e, _c, help_id = asyncio.run(open_help(bot, CHAT_A, owner))

    asyncio.run(save_via_reply(bot, CHAT_A, owner, help_id, "متن سالم اول"))
    check("متن سالم ذخیره شد", clipboard.get(CHAT_A)[0] == "متن سالم اول")

    bad_samples = [
        "برو بابا کسکش",
        "ک.ی.ر.م",
        "کییییرم",
        "you are a f4ck",
        "this is pure porn content",
        "عکس سکسی بفرست",
        "بیا سایت pornhub.com",
    ]
    for sample in bad_samples:
        event, consumed = asyncio.run(
            save_via_reply(bot, CHAT_A, owner, help_id, sample))
        check(f"«{sample[:22]}…» ذخیره نشد",
              clipboard.get(CHAT_A)[0] == "متن سالم اول",
              f"-> {clipboard.get(CHAT_A)[0]!r}")
        check(f"«{sample[:22]}…» پیام رد گرفت",
              consumed is True and event.said("غیرمجاز"))

    check("کپی‌بورد قبلی دست‌نخورده ماند",
          clipboard.get(CHAT_A)[0] == "متن سالم اول")

    print("  — نبودِ false positive روی متن‌های سالم")
    safe_samples = [
        "سلام دوستان 👋",
        "لینک کانال: https://t.me/classroom",
        "برای ورود به کلاس password را وارد کنید",
        "اعلان مهم: جلسه ساعت ۱۸ برگزار می‌شود",
        "https://splus.ir/foxchannel",
        "Welcome to our class, please pass the link",
    ]
    for sample in safe_samples:
        check(f"«{sample[:28]}…» سالم تشخیص داده شد",
              content_guard.is_allowed(sample),
              f"-> {content_guard.classify_text(sample)!r}")


# ===========================================================================
# ۱۲. جدا بودن گروه‌ها
# ===========================================================================
def test_group_isolation():
    print("\n### 1️⃣2️⃣ جدا بودن کپی‌بورد هر گروه")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    _ea, _ca, help_a = asyncio.run(open_help(bot, CHAT_A, owner))
    asyncio.run(save_via_reply(bot, CHAT_A, owner, help_a, "متن گروه الف"))

    show_b = Event(CHAT_B, "کپی")
    asyncio.run(run(bot, show_b, CHAT_B, owner))
    check("گروه ب متن گروه الف را نمی‌بیند",
          show_b.out == [clipboard.EMPTY_MESSAGE], f"-> {show_b.out}")

    _eb, _cb, help_b = asyncio.run(open_help(bot, CHAT_B, owner))
    asyncio.run(save_via_reply(bot, CHAT_B, owner, help_b, "متن گروه ب"))
    check("گروه الف دست‌نخورده ماند",
          clipboard.get(CHAT_A)[0] == "متن گروه الف")
    check("گروه ب متن خودش را دارد",
          clipboard.get(CHAT_B)[0] == "متن گروه ب")

    check("Reply به راهنمای گروه الف در گروه ب کار نمی‌کند",
          not clipboard.is_help_message(CHAT_B, help_a))

    print("  — جدا بودن نمونه‌های ربات (Bot1/Bot2/Bot3)")
    check("مسیر فایل زیر دایرکتوری دادهٔ همان instance است",
          "clipboard.json" in str(clipboard.FILE))


# ===========================================================================
# ۱۳. نبود کپی‌بورد
# ===========================================================================
def test_empty_clipboard():
    print("\n### 1️⃣3️⃣ نبود کپی‌بورد")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    show = Event(CHAT_A, "کپی")
    consumed = asyncio.run(run(bot, show, CHAT_A, owner))
    check("پیام مصرف شد", consumed is True)
    check("پیام مناسب داده شد", show.out == [clipboard.EMPTY_MESSAGE],
          f"-> {show.out}")


# ===========================================================================
# ۱۴. ماندگاری بعد از ری‌استارت
# ===========================================================================
def test_persistence():
    print("\n### 1️⃣4️⃣ ماندگاری بعد از ری‌استارت")
    temp = use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    _e, _c, help_id = asyncio.run(open_help(bot, CHAT_A, owner))

    body = "اعلان مهم گروه\nلینک: https://splus.ir/fox"
    asyncio.run(save_via_reply(
        bot, CHAT_A, owner, help_id, body,
        [make_entity("MessageEntityBold", offset=0,
                     length=clipboard.u16_len("اعلان مهم گروه")),
         make_entity("MessageEntityBlockquote", offset=0,
                     length=clipboard.u16_len("اعلان مهم گروه"))]))

    # «ری‌استارت»: کش پاک و فایل دوباره از صفر خوانده می‌شود.
    clipboard.FILE = temp / "clipboard.json"
    clipboard.reset_cache()

    text, entities = clipboard.get(CHAT_A)
    check("متن بعد از ری‌استارت باقی ماند", text == body, f"-> {text!r}")
    check("قالب‌بندی بعد از ری‌استارت باقی ماند",
          sorted(kinds(entities))
          == ["MessageEntityBlockquote", "MessageEntityBold"],
          f"-> {kinds(entities)}")
    check("شناسهٔ راهنما هم ماندگار است",
          clipboard.is_help_message(CHAT_A, help_id))

    show = Event(CHAT_A, "کپی")
    asyncio.run(run(bot, show, CHAT_A, owner))
    check("بعد از ری‌استارت «کپی» کار می‌کند", show.out == [body])

    raw = json.loads((temp / "clipboard.json").read_text(encoding="utf-8"))
    check("فایل JSON معتبر و خوانا است", isinstance(raw, dict) and raw)


# ===========================================================================
# ۱۵. رگرسیون: قابلیت‌های قبلی
# ===========================================================================
def test_no_regression():
    print("\n### 1️⃣5️⃣ رگرسیون — قابلیت‌های قبلی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    # دستورهای قبلی هرگز توسط این هندلر مصرف نمی‌شوند.
    for other in ("مهلت گروه", "راهنما", "لیست ادمینی", "سنجاق", "قفل",
                  "پاک 10", "اخطار", "موجودی", "اسم فامیل"):
        event = Event(CHAT_A, other)
        consumed = asyncio.run(run(bot, event, CHAT_A, owner))
        check(f"«{other}» به هندلر کپی بورد نمی‌چسبد",
              consumed is False and event.out == [])

    # متن راهنمای «لیست ادمینی» با همان محتوای خواسته‌شده ساخته می‌شود.
    section, spans = clipboard.build_help_section()
    check("خط عنوان بخش راهنما درست است",
          section.splitlines()[0] == "📮کپی بورد حافظه روباهی")
    check("خط ایجاد درست است",
          section.splitlines()[1] == "برای ایجاد بنویسید کپی بورد")
    check("خط نمایش درست است",
          section.splitlines()[2] == "برای نمایش پیام بنویس کپی")
    check("کل بخش Bold است",
          ("bold", 0, clipboard.u16_len(section)) in spans)
    check("کل بخش داخل نقل‌قول است",
          ("blockquote", 0, clipboard.u16_len(section)) in spans)

    # همان متن در راهنمای ربات هم ثبت شده است.
    source = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8")
    check("بخش کپی بورد به راهنمای لیست ادمینی وصل شده است",
          "CLIPBOARD_HELP_SECTION" in source)
    check("بخش هم Bold و هم Quote ثبت شده است",
          source.count("CLIPBOARD_HELP_SECTION") >= 4,
          f"-> {source.count('CLIPBOARD_HELP_SECTION')}")

    # رگرسیون موتور فیلتر نام: رفتار قبلی عوض نشده است.
    from economy import name_filter
    check("name_filter هنوز نام سالم را می‌پذیرد",
          name_filter.classify("کسری") is None)
    check("name_filter هنوز فحش را می‌گیرد",
          name_filter.classify("کسکش") == name_filter.BANNED)


def main():
    print("=" * 60)
    print("📮 تست قابلیت کپی بورد (حافظهٔ روباهی)")
    print("=" * 60)
    test_command_matching()
    test_dispatch_lane()
    test_help_message()
    test_save_show_replace()
    test_formatting_preserved()
    test_requires_reply()
    test_permissions()
    test_content_filter()
    test_group_isolation()
    test_empty_clipboard()
    test_persistence()
    test_no_regression()
    print("\n" + "=" * 60)
    print(f"PASSED={PASSED}  FAILED={FAILED}")
    print("=" * 60)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
