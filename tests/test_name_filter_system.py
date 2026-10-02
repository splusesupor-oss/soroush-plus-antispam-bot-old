"""🚫 «فیلتر اسم» به‌عنوان یک سیستم کاملاً مستقل.

شش محور خواسته‌شده، سرتاسری و روی خودِ pipeline واقعی:

    ۱. متن       — «فیلتر اسم حسین»
    ۲. ایموجی    — «فیلتر اسم 🍆»
    ۳. اولین پیام — همان پیام اول حذف + مجازات
    ۴. لغو فیلتر  — «لغو اسم حسین»
    ۵. لیست      — «لیست فیلتر اسم»
    ۶. جداسازی گروه‌ها
    ۷. استقلال از Advertising Name Moderation

    python tests/test_name_filter_system.py
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

if "splusthon" not in sys.modules:
    _fake = types.ModuleType("splusthon")
    _fake.Button = object
    _fake.types = types.ModuleType("splusthon.types")
    _tl = types.ModuleType("splusthon.tl")
    _tlt = types.ModuleType("splusthon.tl.types")

    class _Ent:
        def __init__(self, offset=0, length=0, **_kw):
            self.offset = offset
            self.length = length

    _tlt.MessageEntityBold = _Ent
    _tlt.MessageEntityBlockquote = _Ent
    _tl.types = _tlt
    _tl.functions = types.ModuleType("splusthon.tl.functions")
    _fake.tl = _tl
    for _name, _mod in (
        ("splusthon", _fake), ("splusthon.tl", _tl),
        ("splusthon.tl.types", _tlt),
        ("splusthon.tl.functions", _tl.functions),
        ("splusthon.types", _fake.types),
    ):
        sys.modules[_name] = _mod

import handlers.message_handler as handler
import modules.ad_name_detector as ad_name_detector
import modules.admin_storage as admin_storage
import modules.name_filters as nf
import modules.owner_check as oc
import modules.punishment_mode as punishment_mode
from handlers.name_filter_handler import handle as handle_name_filter

PASSED = FAILED = 0

CHAT_A = -1001111111111
CHAT_B = -1002222222222
OWNER_ID = 42
ADMIN_ID = 99
OFFENDER_ID = 777
BYSTANDER_ID = 555


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class User:
    def __init__(self, uid, first="U", last=None, username=None):
        self.id = uid
        self.first_name = first
        self.last_name = last
        self.username = username


class Message:
    _n = 100

    def __init__(self, text=""):
        Message._n += 1
        self.id = Message._n
        self.message = text
        self.text = text
        self.entities = []
        self.file = None
        self.media = None
        self.fwd_from = None


class Event:
    def __init__(self, text="سلام", chat_id=CHAT_A, sender=None):
        self.message = Message(text)
        self.is_private = False
        self.chat_id = chat_id
        self.sender = sender or User(OFFENDER_ID, "حسین")
        self.sender_id = self.sender.id
        self.out = False
        self.chat = types.SimpleNamespace(id=chat_id, title="گروه")
        self.replies = []

    async def get_chat(self):
        return self.chat

    async def get_sender(self):
        return self.sender

    async def get_reply_message(self):
        return getattr(self, "replied", None)

    async def reply(self, text, formatting_entities=None, **_kw):
        self.replies.append(text)
        return types.SimpleNamespace(id=1)


class Logger:
    def __init__(self):
        self.info, self.errors = [], []

    def log_info(self, m):
        self.info.append(m)

    def log_error(self, m):
        self.errors.append(m)

    def has(self, needle):
        return any(needle in m for m in self.info)


class DeleteQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, chat_id, ids, priority=1):
        self.calls.append((chat_id, list(ids)))
        return True


class ModerationQueue:
    def __init__(self):
        self.jobs = []

    def enqueue(self, chat_id, kind, user_id=None, timeout_seconds=None,
                operation=None, on_success=None, on_failure=None):
        self.jobs.append({"chat_id": chat_id, "kind": kind,
                          "user_id": user_id, "operation": operation,
                          "on_success": on_success})
        return True

    async def run_all(self):
        for job in list(self.jobs):
            result = await job["operation"]()
            if job["on_success"]:
                await job["on_success"](result)


class AdminActions:
    def __init__(self):
        self.bans, self.mutes = [], []

    async def ban_user(self, chat_id, user_id, reason="", user=None,
                       chat=None):
        if punishment_mode.is_mute(chat_id):
            self.mutes.append((chat_id, user_id))
        else:
            self.bans.append((chat_id, user_id))
        return True


class Bot:
    def __init__(self):
        self.logger = Logger()
        self.punished_users = set()
        self.message_delete_queue = DeleteQueue()
        self.moderation_queue = ModerationQueue()
        self.admin_actions = AdminActions()
        self.outgoing_sender = None
        self.notice_cleanup = None
        self.client = None
        self.bot_account_id = None
        self.reply_input_peer_cache = {}
        self.config_manager = types.SimpleNamespace(
            get=lambda key, default=None: default)


def fresh():
    temp = Path(tempfile.mkdtemp())
    nf.FILE = temp / "name_filters.json"
    nf.reset_cache()
    admin_storage.FILE = temp / "admins.json"
    admin_storage._cache = None
    admin_storage._cache_mtime = None
    punishment_mode._FILE = temp / "punishment.json"
    punishment_mode._cache = None
    punishment_mode._cache_mtime = None
    owner = temp / "owner.json"
    owner.write_text(json.dumps({"user_id": OWNER_ID, "username": "owner"}),
                     encoding="utf-8")
    oc.DEPLOYMENT_FILE = owner
    oc._CACHE_SIGNATURE = None
    oc._CACHE_OWNER = None
    return temp


def command(bot, chat_id, sender, text):
    """دستور را از مسیر واقعی هندلر فیلتر اسم رد می‌کند."""
    event = Event(text, chat_id, sender)
    done = asyncio.run(handle_name_filter(
        bot, event, chat_id, sender.id, sender, text, logger=bot.logger))
    return done, event.replies


def command_reply(bot, chat_id, sender, text, target):
    """دستور را با «ریپلای» روی پیام یک کاربر دیگر اجرا می‌کند."""
    event = Event(text, chat_id, sender)
    event.replied = types.SimpleNamespace(sender=target)
    asyncio.run(handle_name_filter(
        bot, event, chat_id, sender.id, sender, text, logger=bot.logger))
    return event.replies


def deliver(bot, chat_id, sender, text="سلام"):
    """یک پیام عادی گروه را از خودِ handle_new_message رد می‌کند."""
    event = Event(text, chat_id, sender)
    asyncio.run(handler.handle_new_message(bot, event))
    return event


# ===========================================================================
# ۱. متن
# ===========================================================================
def test_text_filter():
    print("\n### 1️⃣ فیلتر متنی")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    done, replies = command(bot, CHAT_A, owner, "فیلتر اسم حسین")
    check("دستور پذیرفته شد", done is True)
    check("پاسخ درست است", replies and "حسین فیلتر شد" in replies[0],
          f"-> {replies}")
    check("در فایل ذخیره شد", nf.list_terms(CHAT_A) == ["حسین"],
          f"-> {nf.list_terms(CHAT_A)}")

    check("نام دقیق match می‌شود",
          nf.match_name(CHAT_A, User(1, "حسین")) == "حسین")
    check("نام مرکب match می‌شود",
          nf.match_name(CHAT_A, User(2, "حسین", "احمدی")) == "حسین")
    check("کشیده و حروف تکراری match می‌شود",
          nf.match_name(CHAT_A, User(3, "حســیییین")) == "حسین")
    check("نیم‌فاصله match می‌شود",
          nf.match_name(CHAT_A, User(4, "ح\u200cسین")) == "حسین")
    check("ی/ک عربی match می‌شود",
          nf.match_name(CHAT_A, User(5, "حسين")) == "حسین")
    check("نام بی‌ربط match نمی‌شود",
          nf.match_name(CHAT_A, User(6, "مریم")) is None)

    done, replies = command(bot, CHAT_A, owner, "فیلتر اسم حسین")
    check("ثبت تکراری رد می‌شود",
          replies and "از قبل" in replies[0], f"-> {replies}")

    stranger = User(BYSTANDER_ID, "رهگذر")
    _done, replies = command(bot, CHAT_A, stranger, "فیلتر اسم علی")
    check("کاربر عادی اجازه ندارد",
          replies and "فقط مالک" in replies[0], f"-> {replies}")
    check("چیزی اضافه نشد", nf.list_terms(CHAT_A) == ["حسین"])

    admin_storage.add_admin(CHAT_A, ADMIN_ID, "adminuser")
    admin = User(ADMIN_ID, "ادمین", username="adminuser")
    command(bot, CHAT_A, admin, "فیلتر اسم علی")
    check("ادمین ثبت‌شده اجازه دارد",
          sorted(nf.list_terms(CHAT_A)) == sorted(["حسین", "علی"]),
          f"-> {nf.list_terms(CHAT_A)}")


# ===========================================================================
# ۲. ایموجی
# ===========================================================================
def test_emoji_filter():
    print("\n### 2️⃣ فیلتر ایموجی")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    done, replies = command(bot, CHAT_A, owner, "فیلتر اسم 🍆")
    check("ایموجی ثبت شد", done and nf.list_terms(CHAT_A) == ["🍆"],
          f"-> {nf.list_terms(CHAT_A)}")
    check("پاسخ ایموجی را نشان می‌دهد",
          replies and "🍆" in replies[0], f"-> {replies}")

    check("نام فقط-ایموجی match می‌شود",
          nf.match_name(CHAT_A, User(1, "🍆")) == "🍆")
    check("ایموجی چسبیده به متن match می‌شود",
          nf.match_name(CHAT_A, User(2, "علی🍆")) == "🍆")
    check("ایموجی با فاصله match می‌شود",
          nf.match_name(CHAT_A, User(3, "علی 🍆 خان")) == "🍆")
    check("ایموجی در نام خانوادگی match می‌شود",
          nf.match_name(CHAT_A, User(4, "رضا", "🍆")) == "🍆")
    check("ایموجی تکراری match می‌شود",
          nf.match_name(CHAT_A, User(5, "🍆🍆🍆")) == "🍆")
    check("Variation Selector فرقی نمی‌کند",
          nf.match_name(CHAT_A, User(6, "ali\ufe0f🍆")) == "🍆")
    check("ایموجی دیگر match نمی‌شود",
          nf.match_name(CHAT_A, User(7, "علی🍎")) is None)
    check("نام بدون ایموجی match نمی‌شود",
          nf.match_name(CHAT_A, User(8, "علی")) is None)

    check("is_emoji_only برای ایموجی درست است", nf.is_emoji_only("🍆"))
    check("is_emoji_only برای متن نادرست است", not nf.is_emoji_only("حسین"))

    command(bot, CHAT_A, owner, "فیلتر اسم 🔥")
    check("چند ایموجی کنار هم ذخیره می‌شوند",
          sorted(nf.list_terms(CHAT_A)) == sorted(["🍆", "🔥"]),
          f"-> {nf.list_terms(CHAT_A)}")
    check("ایموجی دوم هم می‌گیرد",
          nf.match_name(CHAT_A, User(9, "سارا🔥")) == "🔥")


# ===========================================================================
# ۳. اولین پیام → حذف + مجازات
# ===========================================================================
def test_first_message_enforcement():
    print("\n### 3️⃣ اولین پیام: حذف + مجازات")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    command(bot, CHAT_A, owner, "فیلتر اسم حسین")

    offender = User(OFFENDER_ID, "حسین")
    event = deliver(bot, CHAT_A, offender, "سلام بچه‌ها")

    check("گیت مستقل زده شد", bot.logger.has("NAME FILTER HIT"))
    check("همان اولین پیام حذف شد",
          bot.message_delete_queue.calls
          and bot.message_delete_queue.calls[0] == (CHAT_A, [event.message.id]),
          f"-> {bot.message_delete_queue.calls}")
    check("مجازات صف شد",
          len(bot.moderation_queue.jobs) == 1
          and bot.moderation_queue.jobs[0]["user_id"] == OFFENDER_ID,
          f"-> {bot.moderation_queue.jobs}")

    asyncio.run(bot.moderation_queue.run_all())
    check("اخراج اجرا شد (حالت پیش‌فرض)",
          bot.admin_actions.bans == [(CHAT_A, OFFENDER_ID)],
          f"-> {bot.admin_actions.bans}")

    print("  — حالت سکوت")
    fresh()
    bot2 = Bot()
    command(bot2, CHAT_A, owner, "فیلتر اسم حسین")
    punishment_mode.set_mode(CHAT_A, punishment_mode.MODE_MUTE)
    event2 = deliver(bot2, CHAT_A, User(OFFENDER_ID, "حسین"))
    asyncio.run(bot2.moderation_queue.run_all())
    check("سکوت اجرا شد، نه اخراج",
          bot2.admin_actions.mutes and not bot2.admin_actions.bans,
          f"-> mutes={bot2.admin_actions.mutes}")
    check("پیام باز هم حذف شد",
          bot2.message_delete_queue.calls
          and bot2.message_delete_queue.calls[0][1] == [event2.message.id])

    print("  — ایموجی هم روی اولین پیام")
    fresh()
    bot3 = Bot()
    command(bot3, CHAT_A, owner, "فیلتر اسم 🍆")
    event3 = deliver(bot3, CHAT_A, User(321, "علی🍆"))
    check("اولین پیام کاربرِ ایموجی‌دار حذف شد",
          bot3.message_delete_queue.calls
          and bot3.message_delete_queue.calls[0][1] == [event3.message.id],
          f"-> {bot3.message_delete_queue.calls}")
    check("مجازاتش هم صف شد", len(bot3.moderation_queue.jobs) == 1)

    print("  — کاربران معاف و بی‌ربط")
    fresh()
    bot4 = Bot()
    command(bot4, CHAT_A, owner, "فیلتر اسم حسین")
    deliver(bot4, CHAT_A, User(BYSTANDER_ID, "مریم"))
    check("کاربر بی‌ربط مجازات نشد", not bot4.moderation_queue.jobs)
    deliver(bot4, CHAT_A, User(OWNER_ID, "حسین"))
    check("مالک اصلی با همان نام هم معاف است",
          not bot4.moderation_queue.jobs, f"-> {bot4.moderation_queue.jobs}")
    admin_storage.add_admin(CHAT_A, ADMIN_ID, "adminuser")
    deliver(bot4, CHAT_A, User(ADMIN_ID, "حسین", username="adminuser"))
    check("ادمین ثبت‌شده معاف است", not bot4.moderation_queue.jobs)

    print("  — پیام‌های بعدی incident تکراری نمی‌سازند")
    fresh()
    bot5 = Bot()
    command(bot5, CHAT_A, owner, "فیلتر اسم حسین")
    repeat = User(OFFENDER_ID, "حسین")
    deliver(bot5, CHAT_A, repeat, "اول")
    deliver(bot5, CHAT_A, repeat, "دوم")
    deliver(bot5, CHAT_A, repeat, "سوم")
    check("فقط یک مجازات صف شد", len(bot5.moderation_queue.jobs) == 1,
          f"-> {len(bot5.moderation_queue.jobs)}")


# ===========================================================================
# ۴. لغو فیلتر
# ===========================================================================
def test_remove_filter():
    print("\n### 4️⃣ لغو فیلتر")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    command(bot, CHAT_A, owner, "فیلتر اسم حسین")
    command(bot, CHAT_A, owner, "فیلتر اسم 🍆")

    done, replies = command(bot, CHAT_A, owner, "لغو اسم حسین")
    check("دستور «لغو اسم» کار کرد", done is True)
    check("پاسخ درست است",
          replies and "حسین از فیلتر خارج شد" in replies[0], f"-> {replies}")
    check("از لیست حذف شد", nf.list_terms(CHAT_A) == ["🍆"],
          f"-> {nf.list_terms(CHAT_A)}")
    check("دیگر match نمی‌شود",
          nf.match_name(CHAT_A, User(1, "حسین")) is None)
    check("فیلتر دیگر دست‌نخورده ماند",
          nf.match_name(CHAT_A, User(2, "علی🍆")) == "🍆")

    _done, replies = command(bot, CHAT_A, owner, "لغو اسم حسین")
    check("لغو تکراری پیام مناسب می‌دهد",
          replies and "پیدا نشد" in replies[0], f"-> {replies}")

    _done, replies = command(bot, CHAT_A, owner, "حذف فیلتر اسم 🍆")
    check("«حذف فیلتر اسم» مترادف است",
          replies and "از فیلتر خارج شد" in replies[0], f"-> {replies}")
    check("لیست خالی شد", nf.list_terms(CHAT_A) == [])

    command(bot, CHAT_A, owner, "فیلتر اسم حسین")
    stranger = User(BYSTANDER_ID, "رهگذر")
    _done, replies = command(bot, CHAT_A, stranger, "لغو اسم حسین")
    check("کاربر عادی نمی‌تواند لغو کند",
          replies and "فقط مالک" in replies[0], f"-> {replies}")
    check("فیلتر سر جایش است", nf.list_terms(CHAT_A) == ["حسین"])

    print("  — بعد از لغو، enforcement هم متوقف می‌شود")
    command(bot, CHAT_A, owner, "لغو اسم حسین")
    clean = Bot()
    deliver(clean, CHAT_A, User(OFFENDER_ID, "حسین"))
    check("کاربر دیگر مجازات نمی‌شود", not clean.moderation_queue.jobs,
          f"-> {clean.moderation_queue.jobs}")
    check("پیامش هم حذف نشد", not clean.message_delete_queue.calls)


# ===========================================================================
# ۵. لیست فیلتر
# ===========================================================================
def test_list_filters():
    print("\n### 5️⃣ لیست فیلتر اسم")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    _done, replies = command(bot, CHAT_A, owner, "لیست فیلتر اسم")
    check("لیست خالی پیام مناسب دارد",
          replies and "ثبت نشده" in replies[0], f"-> {replies}")

    command(bot, CHAT_A, owner, "فیلتر اسم حسین")
    command(bot, CHAT_A, owner, "فیلتر اسم 🍆")
    command(bot, CHAT_A, owner, "فیلتر اسم علی رضا")

    _done, replies = command(bot, CHAT_A, owner, "لیست فیلتر اسم")
    body = replies[0] if replies else ""
    check("عنوان لیست هست", "لیست فیلتر اسم گروه" in body, f"-> {body!r}")
    for term in ("حسین", "🍆", "علی رضا"):
        check(f"«{term}» در لیست هست", term in body, f"-> {body!r}")
    check("هر عبارت در خط خودش است",
          body.count("•") == 3, f"-> {body!r}")

    text, spans = nf.build_list_message(CHAT_A)
    check("عنوان Bold است",
          any(kind == "bold" and offset == 0 for kind, offset, _ in spans),
          f"-> {spans}")
    check("متن ساخته‌شده همان است", text == body)

    stranger = User(BYSTANDER_ID, "رهگذر")
    _done, replies = command(bot, CHAT_A, stranger, "لیست فیلتر اسم")
    check("کاربر عادی لیست را نمی‌بیند",
          replies and "فقط مالک" in replies[0], f"-> {replies}")


# ===========================================================================
# ۶. جداسازی گروه‌ها
# ===========================================================================
def test_group_isolation():
    print("\n### 6️⃣ جداسازی گروه‌ها")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    command(bot, CHAT_A, owner, "فیلتر اسم حسین")
    command(bot, CHAT_B, owner, "فیلتر اسم 🍆")

    check("گروه الف فقط فیلتر خودش را دارد",
          nf.list_terms(CHAT_A) == ["حسین"], f"-> {nf.list_terms(CHAT_A)}")
    check("گروه ب فقط فیلتر خودش را دارد",
          nf.list_terms(CHAT_B) == ["🍆"], f"-> {nf.list_terms(CHAT_B)}")

    hossein = User(OFFENDER_ID, "حسین")
    emoji_user = User(888, "علی🍆")
    check("حسین در گروه الف می‌خورد",
          nf.match_name(CHAT_A, hossein) == "حسین")
    check("حسین در گروه ب نمی‌خورد",
          nf.match_name(CHAT_B, hossein) is None)
    check("ایموجی در گروه ب می‌خورد",
          nf.match_name(CHAT_B, emoji_user) == "🍆")
    check("ایموجی در گروه الف نمی‌خورد",
          nf.match_name(CHAT_A, emoji_user) is None)

    bot_a = Bot()
    deliver(bot_a, CHAT_B, hossein)
    check("حسین در گروه ب مجازات نمی‌شود", not bot_a.moderation_queue.jobs)
    deliver(bot_a, CHAT_A, hossein)
    check("حسین در گروه الف مجازات می‌شود",
          len(bot_a.moderation_queue.jobs) == 1
          and bot_a.moderation_queue.jobs[0]["chat_id"] == CHAT_A,
          f"-> {bot_a.moderation_queue.jobs}")

    command(bot, CHAT_A, owner, "لغو اسم حسین")
    check("لغو در گروه الف روی گروه ب اثر ندارد",
          nf.list_terms(CHAT_B) == ["🍆"] and nf.list_terms(CHAT_A) == [])

    check("شکل کوتاه و -100 یک گروه‌اند",
          nf.match_name(CHAT_B, emoji_user)
          == nf.match_name(abs(CHAT_B) - 1_000_000_000_000, emoji_user))


# ===========================================================================
# ۷. استقلال از Advertising Name Moderation
# ===========================================================================
def test_independence():
    print("\n### 7️⃣ استقلال کامل")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    command(bot, CHAT_A, owner, "فیلتر اسم حسین")

    nf_src = (ROOT / "modules" / "name_filters.py").read_text(encoding="utf-8")
    ad_src = (ROOT / "modules" / "ad_name_detector.py").read_text(
        encoding="utf-8")

    check("name_filters از ad_name_detector import نمی‌کند",
          "import ad_name_detector" not in nf_src
          and "from modules.ad_name_detector" not in nf_src)
    check("ad_name_detector از name_filters import نمی‌کند",
          "import name_filters" not in ad_src
          and "from modules.name_filters" not in ad_src)

    check("normalize داخل خود ماژول است", callable(nf.normalize))
    check("collapse داخل خود ماژول است", callable(nf.collapse))
    check("تطبیق ایموجی داخل خود ماژول است", callable(nf.is_emoji_only))
    check("display_name داخل خود ماژول است",
          nf.display_name(User(1, "حسین", "احمدی")) == "حسین احمدی")

    user = User(OFFENDER_ID, "حسین")
    check("سیستم مستقل می‌گیرد", nf.match_name(CHAT_A, user) == "حسین")
    check("موتور تبلیغات کاری با آن ندارد",
          ad_name_detector.reason(user, CHAT_A) is None,
          f"-> {ad_name_detector.reason(user, CHAT_A)!r}")
    check("موتور تبلیغات بدون chat_id هم کاری ندارد",
          ad_name_detector.reason(user) is None)

    print("  — ولی الگوهای تبلیغاتی سراسری دست‌نخورده‌اند")
    for label, suspect in (("بیو چک", User(10, "بیو چک")),
                           ("🔞", User(11, "سلام 🔞")),
                           ("پیوی", User(12, "فیلم پی وی"))):
        check(f"«{label}» همچنان تبلیغاتی است",
              ad_name_detector.reason(suspect) is not None)
    check("نام سالم سالم می‌ماند",
          ad_name_detector.reason(User(13, "مریم")) is None)

    src = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8")
    body = src[src.index("async def handle_new_message("):]
    gate = body.index("_nf_term = _name_filter_hit(")
    check("گیت مستقل پیش از گیت تبلیغات است",
          gate < body.index("ad_reason = ad_name_detector.reason("))
    check("گیت مستقل پیش از return مدیای بدون متن است",
          gate < body.index("if not has_text_content and not is_forwarded_media"))
    check("گیت مستقل پیش از موج اسپم است",
          gate < body.index("_queue_big_spam_ban("))
    check("گیت مستقل از name_filters.match_name استفاده می‌کند",
          "name_filters.match_name(chat_id, sender)" in src)
    check("مجازات از enforcement موجود می‌آید (سیستم دوم ساخته نشده)",
          src.count("async def _enforce_ad_name") == 1
          and "bot.moderation_queue.enqueue(" in src
          and "punishment_mode.is_mute(chat_id)" in src)

    print("  — ماندگاری بعد از ری‌استارت")
    nf.reset_cache()
    check("فیلترها از فایل بازخوانی می‌شوند",
          nf.list_terms(CHAT_A) == ["حسین"], f"-> {nf.list_terms(CHAT_A)}")
    payload = json.loads(Path(nf.FILE).read_text(encoding="utf-8"))
    check("فایل JSON معتبر و گروه‌بندی‌شده است",
          isinstance(payload, dict) and len(payload) == 1, f"-> {payload}")


# ===========================================================================
# ۸. دستور تشخیصی «تست فیلتر اسم»
# ===========================================================================
def test_diagnostic_command():
    print("\n### 8️⃣ دستور «تست فیلتر اسم»")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    _done, replies = command(bot, CHAT_A, owner, "تست فیلتر اسم")
    body = replies[0] if replies else ""
    check("روی گروه بدون فیلتر هشدار می‌دهد",
          "هیچ فیلتری ندارد" in body, f"-> {body!r}")
    check("شناسهٔ گروه را نشان می‌دهد", "شناسهٔ گروه" in body, f"-> {body!r}")

    command(bot, CHAT_A, owner, "فیلتر اسم نازگل")
    command(bot, CHAT_A, owner, "فیلتر اسم 😌")

    target = User(70250954, "نازگل", username="nazgol_01")
    replies = command_reply(bot, CHAT_A, owner, "تست فیلتر اسم", target)
    body = replies[0] if replies else ""
    check("روی ریپلای، نام نمایشی را نشان می‌دهد",
          "نام نمایشی : نازگل" in body, f"-> {body!r}")
    check("یوزرنیم را هم نشان می‌دهد",
          "nazgol_01" in body, f"-> {body!r}")
    check("تطبیق را اعلام می‌کند",
          "✅" in body and "نازگل" in body, f"-> {body!r}")
    check("فیلترهای گروه را فهرست می‌کند",
          "نازگل" in body and "😌" in body, f"-> {body!r}")

    clean = User(999, "Hector", username="hfiytc")
    replies = command_reply(bot, CHAT_A, owner, "تست فیلتر اسم", clean)
    body = replies[0] if replies else ""
    check("کاربر سالم ❌ می‌گیرد", "❌" in body, f"-> {body!r}")
    check("نام نرمال‌شده نمایش داده می‌شود",
          "hector" in body, f"-> {body!r}")

    _done, replies = command(bot, CHAT_A, owner, "تست فیلتر اسم نازگل")
    body = replies[0] if replies else ""
    check("با نام متنی هم کار می‌کند", "✅" in body, f"-> {body!r}")

    _done, replies = command(bot, CHAT_A, owner, "لیست فیلتر اسم")
    check("لیست هم شناسهٔ گروه را دارد",
          replies and "شناسهٔ این گروه" in replies[0], f"-> {replies}")

    stranger = User(BYSTANDER_ID, "رهگذر")
    _done, replies = command(bot, CHAT_A, stranger, "تست فیلتر اسم")
    check("کاربر عادی اجازه ندارد",
          replies and "فقط مالک" in replies[0], f"-> {replies}")

    check("دستور با «فیلتر اسم …» قاطی نمی‌شود",
          nf.match_command("تست فیلتر اسم نازگل") == ("test", "نازگل")
          and nf.match_command("فیلتر اسم نازگل") == ("add", "نازگل"))
    check("چیزی به فیلترها اضافه نشد",
          sorted(nf.list_terms(CHAT_A)) == sorted(["نازگل", "😌"]),
          f"-> {nf.list_terms(CHAT_A)}")


# ===========================================================================
# ۹. نام نمایشیِ ناقص («ناشناخته») — همان باگ واقعی گروه
# ===========================================================================
def test_unresolved_display_name():
    print("\n### 9️⃣ نام نمایشی ناقص → resolve دوباره")
    fresh()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    command(bot, CHAT_A, owner, "فیلتر اسم سجاد")

    check("«ناشناخته» جای‌نگهدار شناخته می‌شود",
          nf.is_unresolved("ناشناخته"))
    check("نام خالی هم جای‌نگهدار است", nf.is_unresolved(""))
    check("Unknown هم جای‌نگهدار است", nf.is_unresolved("Unknown"))
    check("Deleted Account هم جای‌نگهدار است",
          nf.is_unresolved("Deleted Account"))
    check("نام واقعی جای‌نگهدار نیست", not nf.is_unresolved("سجاد"))
    check("نام واقعی لاتین هم جای‌نگهدار نیست",
          not nf.is_unresolved("Hector"))

    broken = User(OFFENDER_ID, "ناشناخته", username="Oiiew")
    check("با نام ناقص هیچ فیلتری نمی‌خورد",
          nf.match_name(CHAT_A, broken) is None)

    real = User(OFFENDER_ID, "سجاد", username="Oiiew")

    class ResolvingClient:
        def __init__(self):
            self.calls = []

        async def get_entity(self, probe):
            self.calls.append(probe)
            return real

    bot.client = ResolvingClient()
    event = Event("سلام", CHAT_A, broken)
    asyncio.run(handler.handle_new_message(bot, event))

    check("entity دوباره گرفته شد", bot.client.calls, f"-> {bot.client.calls}")
    check("resolve لاگ شد", bot.logger.has("NAME FILTER RESOLVED"))
    check("بعد از resolve فیلتر خورد", bot.logger.has("NAME FILTER HIT"))
    check("پیامش حذف شد",
          bot.message_delete_queue.calls
          and bot.message_delete_queue.calls[0][1] == [event.message.id],
          f"-> {bot.message_delete_queue.calls}")
    check("مجازاتش صف شد", len(bot.moderation_queue.jobs) == 1,
          f"-> {bot.moderation_queue.jobs}")

    print("  — وقتی resolve هم جواب نمی‌دهد")
    fresh()
    bot2 = Bot()
    command(bot2, CHAT_A, owner, "فیلتر اسم سجاد")

    class FailingClient:
        async def get_entity(self, probe):
            raise RuntimeError("NOT_FOUND")

    bot2.client = FailingClient()
    asyncio.run(handler.handle_new_message(
        bot2, Event("سلام", CHAT_A, User(424242, "ناشناخته", username="x"))))
    check("ربات کرش نمی‌کند و ادامه می‌دهد",
          bot2.logger.has("NAME FILTER RESOLVE FAILED"))
    check("کسی بی‌دلیل مجازات نمی‌شود", not bot2.moderation_queue.jobs)

    print("  — گروه بدون فیلتر هیچ RPC اضافه نمی‌زند")
    fresh()
    bot3 = Bot()

    class CountingClient:
        def __init__(self):
            self.calls = 0

        async def get_entity(self, probe):
            self.calls += 1
            return real

    bot3.client = CountingClient()
    asyncio.run(handler.handle_new_message(
        bot3, Event("سلام", CHAT_B, User(5, "ناشناخته"))))
    check("هیچ get_entity ای صدا زده نشد", bot3.client.calls == 0,
          f"-> {bot3.client.calls}")

    print("  — گزارش «تست فیلتر اسم» هشدار می‌دهد")
    body, _spans = nf.build_test_message(CHAT_A, broken)
    check("گزارش هشدار نام ناقص دارد",
          "قابل خواندن نیست" in body, f"-> {body!r}")


def main():
    print("=" * 62)
    print("🚫 سیستم مستقل فیلتر اسم")
    print("=" * 62)
    test_text_filter()
    test_emoji_filter()
    test_first_message_enforcement()
    test_remove_filter()
    test_list_filters()
    test_group_isolation()
    test_independence()
    test_diagnostic_command()
    test_unresolved_display_name()
    print("\n" + "=" * 62)
    print(f"PASSED={PASSED}  FAILED={FAILED}")
    print("=" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
