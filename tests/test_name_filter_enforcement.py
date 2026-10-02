"""🚫 «فیلتر اسم» → enforcement واقعی روی اولین پیام کاربر.

این تست دقیقاً همان چیزی را می‌سنجد که در گروه واقعی خراب بود:
ثبت فیلتر کار می‌کرد ولی هیچ حذف/سکوت/اخراجی انجام نمی‌شد.

پوشش:
    • «فیلتر اسم حسین» → کاربر «حسین» → همان اولین پیام → enforcement
    • پیام کاربر در صف حذف می‌رود
    • مجازات از همان Advertising Name Moderation فعلی می‌آید
      (moderation_queue + admin_actions.ban_user + punishment_mode)
    • حالت سکوت و حالت اخراج، هر دو
    • پیام‌های بعدی incident تکراری نمی‌سازند
    • مالک/ادمین ثبت‌شده هرگز فیلتر نمی‌شوند
    • جداسازی گروه‌ها
    • گیت قبل از همهٔ return های زودهنگام قرار دارد (ترتیب واقعی کد)

    python tests/test_name_filter_enforcement.py
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

# ---------------------------------------------------------------------------
# splusthon در محیط تست نصب نیست؛ همان stub استاندارد بقیهٔ تست‌ها.
# ---------------------------------------------------------------------------
if "splusthon" not in sys.modules:
    fake = types.ModuleType("splusthon")
    fake.Button = object
    fake.types = types.ModuleType("splusthon.types")
    tl = types.ModuleType("splusthon.tl")
    tl_types = types.ModuleType("splusthon.tl.types")

    class _Ent:
        def __init__(self, offset=0, length=0, **_kwargs):
            self.offset = offset
            self.length = length

    tl_types.MessageEntityBold = _Ent
    tl_types.MessageEntityBlockquote = _Ent
    tl.types = tl_types
    tl.functions = types.ModuleType("splusthon.tl.functions")
    fake.tl = tl
    sys.modules["splusthon"] = fake
    sys.modules["splusthon.tl"] = tl
    sys.modules["splusthon.tl.types"] = tl_types
    sys.modules["splusthon.tl.functions"] = tl.functions
    sys.modules["splusthon.types"] = fake.types

import handlers.message_handler as handler
import modules.admin_storage as admin_storage
import modules.name_filters as nf
import modules.owner_check as oc
import modules.punishment_mode as punishment_mode

PASSED = FAILED = 0

CHAT_A = -1001234567890
CHAT_B = -1009876543210
OWNER_ID = 42424242
ADMIN_ID = 888000222
OFFENDER_ID = 555000777


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


# ===========================================================================
# دوبل‌های سبک
# ===========================================================================
class User:
    def __init__(self, uid, first="U", last=None, username=None):
        self.id = uid
        self.first_name = first
        self.last_name = last
        self.username = username


class Message:
    _next = 7000

    def __init__(self, text=""):
        Message._next += 1
        self.id = Message._next
        self.message = text
        self.text = text
        self.entities = []


class Event:
    def __init__(self, text="سلام"):
        self.message = Message(text)
        self.is_private = False
        self.replies = []

    async def reply(self, text, formatting_entities=None, **kwargs):
        self.replies.append(text)
        return types.SimpleNamespace(id=999)


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

    def enqueue(self, chat_id, message_ids, priority=1):
        self.calls.append((chat_id, list(message_ids), priority))
        return True


class ModerationQueue:
    """صف مجازات واقعی را تقلید می‌کند و اجازه می‌دهد اجرا شود."""

    def __init__(self, accept=True):
        self.jobs = []
        self.accept = accept

    def enqueue(self, chat_id, kind, user_id=None, timeout_seconds=None,
                operation=None, on_success=None, on_failure=None):
        if not self.accept:
            return False
        self.jobs.append({
            "chat_id": chat_id, "kind": kind, "user_id": user_id,
            "operation": operation, "on_success": on_success,
            "on_failure": on_failure,
        })
        return True

    async def run_all(self):
        for job in list(self.jobs):
            result = await job["operation"]()
            if job["on_success"]:
                await job["on_success"](result)


class AdminActions:
    """همان قرارداد ban_user واقعی: خودش punishment_mode را می‌خواند."""

    def __init__(self):
        self.bans = []
        self.mutes = []

    async def ban_user(self, chat_id, user_id, reason="", user=None,
                       chat=None):
        if punishment_mode.is_mute(chat_id):
            self.mutes.append((chat_id, user_id, reason))
        else:
            self.bans.append((chat_id, user_id, reason))
        return True


class Bot:
    def __init__(self, accept_queue=True):
        self.logger = Logger()
        self.punished_users = set()
        self.message_delete_queue = DeleteQueue()
        self.moderation_queue = ModerationQueue(accept_queue)
        self.admin_actions = AdminActions()
        self.outgoing_sender = None
        self.notice_cleanup = None
        self.client = None


def use_temp_files():
    temp = Path(tempfile.mkdtemp())

    nf.FILE = temp / "name_filters.json"
    nf.reset_cache()

    admin_storage.FILE = temp / "admins.json"
    admin_storage._cache = None
    admin_storage._cache_mtime = None

    punishment_mode._FILE = temp / "punishment_mode.json"
    punishment_mode._cache = None
    punishment_mode._cache_mtime = None

    owner_file = temp / "owner.json"
    owner_file.write_text(
        json.dumps({"user_id": OWNER_ID, "username": "aifox"}),
        encoding="utf-8",
    )
    oc.DEPLOYMENT_FILE = owner_file
    oc._CACHE_SIGNATURE = None
    oc._CACHE_OWNER = None
    return temp


def register_filter(chat_id, term):
    ok, problem, _display = nf.add(chat_id, term)
    assert ok, problem
    return ok


# ===========================================================================
# ۱. گیت تشخیص
# ===========================================================================
def test_gate_detection():
    print("\n### 1️⃣ گیت: چه کسی فیلتر می‌شود")
    use_temp_files()
    bot = Bot()
    register_filter(CHAT_A, "حسین")

    offender = User(OFFENDER_ID, "حسین")
    check("کاربر «حسین» تشخیص داده می‌شود",
          handler._name_filter_hit(bot, CHAT_A, OFFENDER_ID, offender)
          == "حسین")
    check("نام غیرمرتبط تشخیص داده نمی‌شود",
          handler._name_filter_hit(bot, CHAT_A, 11, User(11, "مریم")) is None)
    check("مالک اصلی ربات معاف است",
          handler._name_filter_hit(
              bot, CHAT_A, OWNER_ID, User(OWNER_ID, "حسین")) is None)

    admin_storage.add_admin(CHAT_A, ADMIN_ID, "foxadmin")
    check("ادمین ثبت‌شده معاف است",
          handler._name_filter_hit(
              bot, CHAT_A, ADMIN_ID,
              User(ADMIN_ID, "حسین", username="foxadmin")) is None)
    check("sender نامشخص خطا نمی‌دهد",
          handler._name_filter_hit(bot, CHAT_A, 0, None) is None)
    check("گروه بدون فیلتر، کسی را نمی‌گیرد",
          handler._name_filter_hit(bot, CHAT_B, OFFENDER_ID, offender) is None)


# ===========================================================================
# ۲. enforcement واقعی روی اولین پیام
# ===========================================================================
def test_first_message_ban():
    print("\n### 2️⃣ اولین پیام → حذف پیام + اخراج (حالت پیش‌فرض)")
    use_temp_files()
    bot = Bot()
    register_filter(CHAT_A, "حسین")
    offender = User(OFFENDER_ID, "حسین")
    event = Event("سلام بچه‌ها")

    term = handler._name_filter_hit(bot, CHAT_A, OFFENDER_ID, offender)
    check("فیلتر خورد", term == "حسین")

    consumed = asyncio.run(handler._enforce_ad_name(
        bot, event, CHAT_A, OFFENDER_ID, offender, f"فیلتر اسم: {term}"))
    check("رویداد مصرف شد", consumed is True)

    # ۴. پیام کاربر حذف شود
    check("پیام کاربر در صف حذف رفت",
          bot.message_delete_queue.calls
          and bot.message_delete_queue.calls[0][1] == [event.message.id],
          f"-> {bot.message_delete_queue.calls}")
    check("لاگ حذف ثبت شد",
          bot.logger.has("AD NAME MESSAGE DELETE QUEUED"))

    # ۶. همان سیستم مجازات فعلی
    check("مجازات در صف moderation رفت", len(bot.moderation_queue.jobs) == 1,
          f"-> {bot.moderation_queue.jobs}")
    job = bot.moderation_queue.jobs[0]
    check("نوع کار «ban» است", job["kind"] == "ban")
    check("برای همان کاربر است", job["user_id"] == OFFENDER_ID)
    check("incident قفل شد", bool(bot.punished_users))
    check("لاگ استاندارد نام تبلیغاتی ثبت شد",
          bot.logger.has("AD NAME BAN QUEUED"))

    asyncio.run(bot.moderation_queue.run_all())
    check("ban_user واقعاً اجرا شد",
          bot.admin_actions.bans == [(CHAT_A, OFFENDER_ID, "نام تبلیغاتی")],
          f"-> {bot.admin_actions.bans}")
    check("اعلان بعد از موفقیت فرستاده شد",
          any("اخراج شد" in m for m in event.replies), f"-> {event.replies}")
    check("لاگ پایان ثبت شد", bot.logger.has("AD NAME BAN FINISHED"))


def test_first_message_mute_mode():
    print("\n### 3️⃣ حالت «تغییر مجازات» = سکوت")
    use_temp_files()
    bot = Bot()
    register_filter(CHAT_A, "حسین")
    punishment_mode.set_mode(CHAT_A, punishment_mode.MODE_MUTE)
    check("حالت گروه روی سکوت است", punishment_mode.is_mute(CHAT_A))

    offender = User(OFFENDER_ID, "حسین")
    event = Event("سلام")
    asyncio.run(handler._enforce_ad_name(
        bot, event, CHAT_A, OFFENDER_ID, offender, "فیلتر اسم: حسین"))
    asyncio.run(bot.moderation_queue.run_all())

    check("به‌جای اخراج، سکوت اجرا شد",
          bot.admin_actions.mutes and not bot.admin_actions.bans,
          f"-> mutes={bot.admin_actions.mutes} bans={bot.admin_actions.bans}")
    check("پیام کاربر باز هم حذف شد",
          bot.message_delete_queue.calls
          and bot.message_delete_queue.calls[0][1] == [event.message.id])
    check("متن اعلان «سکوت دائم» است",
          any("سکوت دائم" in m for m in event.replies), f"-> {event.replies}")


def test_duplicate_incident():
    print("\n### 4️⃣ پیام‌های بعدی incident تکراری نمی‌سازند")
    use_temp_files()
    bot = Bot()
    register_filter(CHAT_A, "حسین")
    offender = User(OFFENDER_ID, "حسین")

    first = Event("پیام اول")
    asyncio.run(handler._enforce_ad_name(
        bot, first, CHAT_A, OFFENDER_ID, offender, "فیلتر اسم: حسین"))
    second = Event("پیام دوم")
    consumed = asyncio.run(handler._enforce_ad_name(
        bot, second, CHAT_A, OFFENDER_ID, offender, "فیلتر اسم: حسین"))

    check("پیام دوم هم مصرف شد", consumed is True)
    check("فقط یک مجازات در صف است", len(bot.moderation_queue.jobs) == 1,
          f"-> {len(bot.moderation_queue.jobs)}")
    check("لاگ تکراری ثبت شد",
          bot.logger.has("AD NAME INCIDENT DUPLICATE SKIPPED"))


def test_queue_rejection_releases_lock():
    print("\n### 5️⃣ شکست صف، قفل دائمی نمی‌سازد")
    use_temp_files()
    bot = Bot(accept_queue=False)
    register_filter(CHAT_A, "حسین")
    offender = User(OFFENDER_ID, "حسین")
    asyncio.run(handler._enforce_ad_name(
        bot, Event("سلام"), CHAT_A, OFFENDER_ID, offender, "فیلتر اسم: حسین"))
    check("قفل incident آزاد شد", not bot.punished_users)
    check("لاگ مناسب ثبت شد",
          bot.logger.has("AD NAME INCIDENT QUEUE DUPLICATE"))


def test_group_isolation_enforcement():
    print("\n### 6️⃣ جداسازی گروه‌ها در enforcement")
    use_temp_files()
    bot = Bot()
    register_filter(CHAT_A, "حسین")
    offender = User(OFFENDER_ID, "حسین")

    check("در گروه الف فیلتر می‌شود",
          handler._name_filter_hit(bot, CHAT_A, OFFENDER_ID, offender)
          == "حسین")
    check("در گروه ب فیلتر نمی‌شود",
          handler._name_filter_hit(bot, CHAT_B, OFFENDER_ID, offender) is None)


def test_global_ad_name_still_works():
    print("\n### 7️⃣ رگرسیون: الگوهای سراسری نام تبلیغاتی")
    use_temp_files()
    bot = Bot()
    offender = User(321, "بیو چک")
    event = Event("سلام")
    from modules import ad_name_detector
    reason = ad_name_detector.reason(offender, CHAT_A)
    check("نام تبلیغاتی سراسری هنوز تشخیص داده می‌شود", bool(reason))
    asyncio.run(handler._enforce_ad_name(
        bot, event, CHAT_A, 321, offender, reason))
    asyncio.run(bot.moderation_queue.run_all())
    check("همان مسیر مجازات اجرا شد",
          bot.admin_actions.bans == [(CHAT_A, 321, "نام تبلیغاتی")],
          f"-> {bot.admin_actions.bans}")
    check("پیامش هم حذف شد", bool(bot.message_delete_queue.calls))


# ===========================================================================
# ۸. ترتیب واقعی کد: گیت قبل از return های زودهنگام
# ===========================================================================
def test_gate_runs_before_early_returns():
    print("\n### 8️⃣ گیت قبل از همهٔ return های زودهنگام است")
    full = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8")
    # فقط بدنهٔ handle_new_message بررسی می‌شود، وگرنه تعریف توابع
    # کمکی در بالای فایل با محل *فراخوانی* آن‌ها اشتباه گرفته می‌شود.
    body_start = full.index("async def handle_new_message(")
    source = full[body_start:]
    gate = source.index("_nf_term = _name_filter_hit(")

    later_markers = {
        "return مدیای بدون متن":
            "if not has_text_content and not is_forwarded_media",
        "موج اسپم (_queue_big_spam_ban)": "_queue_big_spam_ban(",
        "حذف فوروارد": "_handle_forwarded_group_message(",
        "قفل اسپم": "reason=spam_lock",
        "گیت نام تبلیغاتی سراسری": "ad_reason = ad_name_detector.reason(",
        "مسیر دستورها (کپی بورد)": "handle_clipboard(",
        "مسیر دستور فیلتر اسم": "handle_name_filter(",
    }
    for label, marker in later_markers.items():
        position = source.index(marker)
        check(f"گیت پیش از «{label}» است", gate < position,
              f"gate={gate} marker={position}")

    check("گیت از _enforce_ad_name استفاده می‌کند (سیستم مجازات جدید نیست)",
          "await _enforce_ad_name(" in source
          and full.count("async def _enforce_ad_name") == 1)
    check("هر دو گیت یک تابع enforcement مشترک دارند",
          source.count("await _enforce_ad_name(") == 2,
          f"-> {source.count('await _enforce_ad_name(')}")


# ===========================================================================
# ۹. end-to-end روی خودِ handle_new_message واقعی
# ===========================================================================
def test_end_to_end_real_pipeline():
    print("\n### 9️⃣ end-to-end: handle_new_message واقعی")
    use_temp_files()
    register_filter(CHAT_A, "حسین")

    class RealEvent(Event):
        def __init__(self, text="سلام"):
            super().__init__(text)
            self.chat_id = CHAT_A
            self.sender = User(OFFENDER_ID, "حسین")
            self.sender_id = OFFENDER_ID
            self.out = False
            self.chat = types.SimpleNamespace(id=CHAT_A, title="گروه تست")
            self.message.file = None
            self.message.media = None
            self.message.fwd_from = None

        async def get_chat(self):
            return self.chat

        async def get_sender(self):
            return self.sender

    bot = Bot()
    bot.bot_account_id = None
    bot.reply_input_peer_cache = {}
    bot.config_manager = types.SimpleNamespace(get=lambda key, default=None: default)

    event = RealEvent("سلام بچه‌ها")
    asyncio.run(handler.handle_new_message(bot, event))

    check("pipeline واقعی گیت را زد", bot.logger.has("NAME FILTER HIT"))
    check("pipeline واقعی پیام را حذف کرد",
          bot.message_delete_queue.calls
          and bot.message_delete_queue.calls[0][1] == [event.message.id],
          f"-> {bot.message_delete_queue.calls}")
    check("pipeline واقعی مجازات را صف کرد",
          len(bot.moderation_queue.jobs) == 1
          and bot.moderation_queue.jobs[0]["user_id"] == OFFENDER_ID,
          f"-> {bot.moderation_queue.jobs}")

    clean = Bot()
    clean.bot_account_id = None
    clean.reply_input_peer_cache = {}
    clean.config_manager = types.SimpleNamespace(
        get=lambda key, default=None: default)

    class CleanEvent(RealEvent):
        def __init__(self):
            super().__init__("سلام")
            self.sender = User(314159, "مریم")
            self.sender_id = 314159

    asyncio.run(handler.handle_new_message(clean, CleanEvent()))
    check("کاربر بی‌ربط مجازات نشد",
          not clean.moderation_queue.jobs,
          f"-> {clean.moderation_queue.jobs}")


def main():
    print("=" * 60)
    print("🚫 تست enforcement فیلتر اسم")
    print("=" * 60)
    test_gate_detection()
    test_first_message_ban()
    test_first_message_mute_mode()
    test_duplicate_incident()
    test_queue_rejection_releases_lock()
    test_group_isolation_enforcement()
    test_global_ad_name_still_works()
    test_gate_runs_before_early_returns()
    test_end_to_end_real_pipeline()
    print("\n" + "=" * 60)
    print(f"PASSED={PASSED}  FAILED={FAILED}")
    print("=" * 60)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
