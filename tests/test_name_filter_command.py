"""🚫 «فیلتر اسم» — تست کامل و مستقل.

پوشش:
    • متن فارسی: «فیلتر اسم حسین»
    • ایموجی: «فیلتر اسم 🍆» و «لغو اسم 🍆»
    • حذف: «لغو اسم …» و «حذف فیلتر اسم …» فقط همان یک عبارت را بردارد
    • «لیست فیلتر اسم»
    • اولین پیامِ کاربرِ فیلترشده → همان enforcement نام تبلیغاتی
    • دسترسی: فقط مالک ثبت‌شده و ادمین ثبت‌شده
    • جداسازی کامل گروه‌ها
    • استفاده از همان normalization موتور فعلی (کشیده/تکرار/ی و ک عربی)
    • متن خروجی: Bold داخل نقل‌قول شیشه‌ای
    • رگرسیون: الگوهای سراسری نام تبلیغاتی دست‌نخورده‌اند

    python tests/test_name_filter_command.py
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import handlers.name_filter_handler as nfh
import modules.admin_storage as admin_storage
import modules.ad_name_detector as ad_name_detector
import modules.group_storage as gs
import modules.name_filters as nf
import modules.owner_check as oc
from modules.group_dispatch import LANE_ADMIN, LANE_COMMAND, classify_priority

PASSED = FAILED = 0

CHAT_A = -1001234567890
CHAT_B = -1009876543210
OWNER_ID = 42424242
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


class User:
    def __init__(self, uid, first="U", last=None, username=None):
        self.id = uid
        self.first_name = first
        self.last_name = last
        self.username = username


class Message:
    _next = 2000

    def __init__(self, text=""):
        Message._next += 1
        self.id = Message._next
        self.message = text
        self.text = text
        self.entities = []
        self.reply_to_msg_id = None
        self.reply_to = None


class Event:
    def __init__(self, text="", is_private=False):
        self.message = Message(text)
        self.is_private = is_private
        self.out = []
        self.out_entities = []

    async def reply(self, text, formatting_entities=None, **kwargs):
        self.out.append(text)
        self.out_entities.append(list(formatting_entities or []))
        return None

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


def use_temp_files():
    temp = Path(tempfile.mkdtemp())

    nf.FILE = temp / "name_filters.json"
    nf.reset_cache()

    admin_storage.FILE = temp / "admins.json"
    admin_storage._cache = None
    admin_storage._cache_mtime = None

    gs.FILE = temp / "groups.json"
    gs._cache = None
    gs._cache_mtime = None

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


def send(bot, chat_id, sender, text):
    event = Event(text)
    clean = " ".join(str(text).split())
    consumed = asyncio.run(nfh.handle(
        bot, event, chat_id, sender.id, sender, clean, bot.logger))
    return event, consumed


# ===========================================================================
# تطبیق دستور و routing
# ===========================================================================
def test_command_matching():
    print("\n### 🎯 تطبیق دستورها")
    check("«فیلتر اسم حسین» → add",
          nf.match_command("فیلتر اسم حسین") == ("add", "حسین"))
    check("«فیلتر اسم 🍆» → add",
          nf.match_command("فیلتر اسم 🍆") == ("add", "🍆"))
    check("«لغو اسم حسین» → remove",
          nf.match_command("لغو اسم حسین") == ("remove", "حسین"))
    check("«لغو اسم 🍆» → remove",
          nf.match_command("لغو اسم 🍆") == ("remove", "🍆"))
    check("«حذف فیلتر اسم حسین» → remove",
          nf.match_command("حذف فیلتر اسم حسین") == ("remove", "حسین"))
    check("«لیست فیلتر اسم» → list",
          nf.match_command("لیست فیلتر اسم") == ("list", None))
    check("چند کلمه‌ای پذیرفته می‌شود",
          nf.match_command("فیلتر اسم فروش ویژه") == ("add", "فروش ویژه"))
    check("فاصلهٔ اضافه پذیرفته می‌شود",
          nf.match_command("  فیلتر   اسم    حسین ") == ("add", "حسین"))
    check("ی/ک عربی پذیرفته می‌شود",
          nf.match_command("فيلتر اسم حسين") == ("add", "حسین"))

    for other in ("فیلتر کلمه", "/فیلتر کلمه", "فیلترها", "اسم فامیل",
                  "لیست ادمینی", "کپی", "کپی بورد", "سلام حسین",
                  "فیلترشکن", "لغو ادمین", "لغو vip"):
        check(f"«{other}» تطبیق نمی‌کند",
              nf.match_command(other) is None,
              f"-> {nf.match_command(other)!r}")


def test_dispatch_lane():
    print("\n### 🚦 لاین پردازش")
    for command in ("فیلتر اسم حسین", "لغو اسم 🍆", "حذف فیلتر اسم حسین",
                    "لیست فیلتر اسم"):
        check(f"«{command}» از لاین admin می‌رود",
              classify_priority(command)[1] == LANE_ADMIN)
    check("«راهنما» همچنان command است",
          classify_priority("راهنما")[1] == LANE_COMMAND)
    check("«لغو» تنها، دستور فیلتر اسم نیست",
          classify_priority("لغو")[1] == LANE_ADMIN)


# ===========================================================================
# افزودن و حذف
# ===========================================================================
def test_add_and_remove_text():
    print("\n### ➕➖ افزودن و حذف عبارت متنی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    event, consumed = send(bot, CHAT_A, owner, "فیلتر اسم حسین")
    check("پیام مصرف شد", consumed is True)
    check("متن تأیید دقیقاً درست است",
          event.out == ["نام : حسین فیلتر شد"], f"-> {event.out}")
    check("در لیست گروه ثبت شد", nf.list_terms(CHAT_A) == ["حسین"])

    names = kinds(event.out_entities[0])
    check("کل متن داخل نقل‌قول است",
          "MessageEntityBlockquote" in names, f"-> {names}")
    check("کل متن Bold است", "MessageEntityBold" in names, f"-> {names}")
    for entity in event.out_entities[0]:
        check(f"{type(entity).__name__} کل متن را می‌پوشاند",
              decode_span(event.out[0], entity.offset, entity.length)
              == "نام : حسین فیلتر شد")

    again, _c = send(bot, CHAT_A, owner, "فیلتر اسم حسین")
    check("تکراری دوباره ثبت نشد", nf.list_terms(CHAT_A) == ["حسین"])
    check("پیام «از قبل هست» داده شد", again.said("از قبل"))

    removed, _c = send(bot, CHAT_A, owner, "لغو اسم حسین")
    check("متن حذف دقیقاً درست است",
          removed.out == ["نام : حسین از فیلتر خارج شد"], f"-> {removed.out}")
    check("از لیست حذف شد", nf.list_terms(CHAT_A) == [])
    names = kinds(removed.out_entities[0])
    check("پیام حذف هم Bold داخل نقل‌قول است",
          "MessageEntityBold" in names and "MessageEntityBlockquote" in names,
          f"-> {names}")

    missing, _c = send(bot, CHAT_A, owner, "لغو اسم حسین")
    check("حذف عبارت ناموجود پیام مناسب می‌دهد",
          missing.said("پیدا نشد"))

    # «حذف فیلتر اسم» هم همان کار را می‌کند
    send(bot, CHAT_A, owner, "فیلتر اسم رضا")
    send(bot, CHAT_A, owner, "حذف فیلتر اسم رضا")
    check("«حذف فیلتر اسم» هم حذف می‌کند", nf.list_terms(CHAT_A) == [])


def test_remove_only_one():
    print("\n### 🎯 حذف فقط همان یک عبارت")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    for term in ("حسین", "رضا", "🍆", "فروش ویژه"):
        send(bot, CHAT_A, owner, f"فیلتر اسم {term}")
    check("هر چهار عبارت ثبت شدند",
          nf.list_terms(CHAT_A) == ["حسین", "رضا", "🍆", "فروش ویژه"],
          f"-> {nf.list_terms(CHAT_A)}")

    send(bot, CHAT_A, owner, "لغو اسم حسین")
    check("فقط «حسین» حذف شد",
          nf.list_terms(CHAT_A) == ["رضا", "🍆", "فروش ویژه"],
          f"-> {nf.list_terms(CHAT_A)}")

    send(bot, CHAT_A, owner, "لغو اسم 🍆")
    check("فقط ایموجی حذف شد",
          nf.list_terms(CHAT_A) == ["رضا", "فروش ویژه"],
          f"-> {nf.list_terms(CHAT_A)}")


def test_emoji():
    print("\n### 🍆 فیلتر ایموجی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    event, _c = send(bot, CHAT_A, owner, "فیلتر اسم 🍆")
    check("ایموجی ثبت شد", nf.list_terms(CHAT_A) == ["🍆"])
    check("متن تأیید ایموجی را نشان می‌دهد",
          event.out == ["نام : 🍆 فیلتر شد"], f"-> {event.out}")

    user = User(STRANGER_ID, "علی 🍆")
    check("نام دارای ایموجی match می‌شود",
          nf.match_name(CHAT_A, user) == "🍆")
    check("نام بدون ایموجی match نمی‌شود",
          nf.match_name(CHAT_A, User(STRANGER_ID, "علی")) is None)

    removed, _c = send(bot, CHAT_A, owner, "لغو اسم 🍆")
    check("متن حذف ایموجی درست است",
          removed.out == ["نام : 🍆 از فیلتر خارج شد"], f"-> {removed.out}")
    check("بعد از لغو دیگر match نمی‌شود",
          nf.match_name(CHAT_A, user) is None)


def test_list_command():
    print("\n### 📋 «لیست فیلتر اسم»")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    empty, consumed = send(bot, CHAT_A, owner, "لیست فیلتر اسم")
    check("پیام مصرف شد", consumed is True)
    check("لیست خالی پیام مناسب دارد",
          empty.out == [nf.EMPTY_LIST_MESSAGE], f"-> {empty.out}")

    send(bot, CHAT_A, owner, "فیلتر اسم حسین")
    send(bot, CHAT_A, owner, "فیلتر اسم 🍆")
    listed, _c = send(bot, CHAT_A, owner, "لیست فیلتر اسم")
    check("هر دو عبارت در لیست هستند",
          "حسین" in listed.out[0] and "🍆" in listed.out[0],
          f"-> {listed.out}")
    check("عنوان لیست Bold است",
          kinds(listed.out_entities[0]) == ["MessageEntityBold"],
          f"-> {kinds(listed.out_entities[0])}")


# ===========================================================================
# تطبیق نام + همان normalization موتور فعلی
# ===========================================================================
def test_matching_uses_existing_normalization():
    print("\n### 🔍 تطبیق نام با همان normalization فعلی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    send(bot, CHAT_A, owner, "فیلتر اسم حسین")

    matching = [
        ("نام ساده", User(1, "حسین")),
        ("نام و فامیل", User(2, "حسین", "محمدی")),
        ("نام داخل عبارت", User(3, "آقا حسین گل")),
        ("کشیده (tatweel)", User(4, "حســیــن")),
        ("حروف تکراری", User(5, "حسییییین")),
        ("ی و ک عربی", User(6, "حسين")),
        ("نیم‌فاصله/علائم", User(7, "حسین_آقا")),
    ]
    for label, user in matching:
        check(f"{label} فیلتر می‌شود",
              nf.match_name(CHAT_A, user) == "حسین",
              f"-> {nf.match_name(CHAT_A, user)!r}")

    for label, user in (("نام دیگر", User(10, "رضا")),
                        ("نام خالی", User(11, "")),
                        ("کاربر بی‌نام", User(12, None))):
        check(f"{label} فیلتر نمی‌شود",
              nf.match_name(CHAT_A, user) is None,
              f"-> {nf.match_name(CHAT_A, user)!r}")

    # یوزرنیم هم بررسی می‌شود (مثل موتور فعلی).
    send(bot, CHAT_A, owner, "فیلتر اسم shopad")
    check("یوزرنیم هم فیلتر می‌شود",
          nf.match_name(CHAT_A, User(13, "Ali", None, "myshopad")) == "shopad")


def test_detector_integration():
    print("\n### 🔗 استقلال کامل از موتور نام تبلیغاتی")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    send(bot, CHAT_A, owner, "فیلتر اسم حسین")

    user = User(STRANGER_ID, "حسین")
    check("سیستم مستقل، کاربر فیلترشده را می‌گیرد",
          nf.match_name(CHAT_A, user) == "حسین")
    check("موتور نام تبلیغاتی دیگر درگیر نیست",
          ad_name_detector.reason(user, CHAT_A) is None,
          f"-> {ad_name_detector.reason(user, CHAT_A)!r}")
    check("name_filters هیچ import ی از ad_name_detector ندارد",
          "from modules import ad_name_detector"
          not in (ROOT / "modules" / "name_filters.py").read_text(
              encoding="utf-8"))
    check("ad_name_detector هیچ import ی از name_filters ندارد",
          "from modules import name_filters"
          not in (ROOT / "modules" / "ad_name_detector.py").read_text(
              encoding="utf-8"))
    check("نرمال‌سازی داخل خود ماژول است",
          callable(nf.normalize) and callable(nf.collapse)
          and nf.normalize("حســیــن") == "حسین")

    print("  — رگرسیون: الگوهای سراسری نام تبلیغاتی دست‌نخورده‌اند")
    for label, suspect in (("بیو چک", User(20, "بیو چک")),
                           ("🔞", User(21, "سلام 🔞")),
                           ("فیلم پی", User(22, "فیلم پی وی"))):
        check(f"«{label}» همچنان تبلیغاتی است",
              ad_name_detector.reason(suspect) is not None)
    check("نام سالم همچنان سالم است",
          ad_name_detector.reason(User(23, "مریم")) is None)
    check("فیلتر اسم روی نام سالم اثر ندارد",
          nf.match_name(CHAT_A, User(24, "مریم")) is None)


def test_first_message_enforcement():
    print("\n### ⚡ اولین پیام کاربر فیلترشده")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")
    send(bot, CHAT_A, owner, "فیلتر اسم حسین")

    offender = User(STRANGER_ID, "حسین")
    check("ادمین نیست",
          not admin_storage.is_admin(CHAT_A, offender.id, None))
    check("همان اولین پیام match می‌شود",
          nf.match_name(CHAT_A, offender) == "حسین")

    source = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8")
    check("گیت مستقل فیلتر اسم در message_handler هست",
          "_name_filter_hit(" in source
          and "name_filters.match_name(chat_id, sender)" in source)
    check("گیت مستقل از name_filters استفاده می‌کند، نه ad_name_detector",
          "from modules import name_filters" in source)
    check("فقط برای مجازات از enforcement موجود استفاده می‌شود",
          "AD NAME BAN QUEUED" in source
          and "punishment_mode.is_mute(chat_id)" in source)

def test_permissions():
    print("\n### 🔐 دسترسی: فقط مالک ثبت‌شده و ادمین ثبت‌شده")
    use_temp_files()
    bot = Bot()
    stranger = User(STRANGER_ID, "رهگذر")
    admin = User(ADMIN_ID, "ادمین", username="foxadmin")

    for command in ("فیلتر اسم حسین", "لغو اسم حسین", "لیست فیلتر اسم"):
        event, consumed = send(bot, CHAT_A, stranger, command)
        check(f"کاربر عادی «{command}» را نمی‌تواند اجرا کند",
              consumed is True and event.said("فقط مالک"))
    check("کاربر عادی چیزی ثبت نکرد", nf.list_terms(CHAT_A) == [])

    admin_storage.add_admin(CHAT_A, ADMIN_ID, "foxadmin")
    event, _c = send(bot, CHAT_A, admin, "فیلتر اسم حسین")
    check("ادمین ثبت‌شده می‌تواند اضافه کند",
          nf.list_terms(CHAT_A) == ["حسین"], f"-> {nf.list_terms(CHAT_A)}")
    event, _c = send(bot, CHAT_A, admin, "لغو اسم حسین")
    check("ادمین ثبت‌شده می‌تواند حذف کند", nf.list_terms(CHAT_A) == [])

    # ادمینِ گروه الف در گروه ب ادمین نیست.
    event, _c = send(bot, CHAT_B, admin, "فیلتر اسم حسین")
    check("ادمین گروه الف در گروه ب مجاز نیست",
          event.said("فقط مالک") and nf.list_terms(CHAT_B) == [])

    owner = User(OWNER_ID, "مالک")
    send(bot, CHAT_B, owner, "فیلتر اسم حسین")
    check("مالک ثبت‌شده در هر گروه مجاز است",
          nf.list_terms(CHAT_B) == ["حسین"])


def test_group_isolation():
    print("\n### 🏘️ جداسازی گروه‌ها")
    use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    send(bot, CHAT_A, owner, "فیلتر اسم حسین")
    send(bot, CHAT_B, owner, "فیلتر اسم رضا")

    check("گروه الف فقط فیلتر خودش را دارد",
          nf.list_terms(CHAT_A) == ["حسین"], f"-> {nf.list_terms(CHAT_A)}")
    check("گروه ب فقط فیلتر خودش را دارد",
          nf.list_terms(CHAT_B) == ["رضا"], f"-> {nf.list_terms(CHAT_B)}")

    hossein = User(1, "حسین")
    reza = User(2, "رضا")
    check("«حسین» در گروه الف فیلتر است",
          nf.match_name(CHAT_A, hossein) == "حسین")
    check("«حسین» در گروه ب فیلتر نیست",
          nf.match_name(CHAT_B, hossein) is None)
    check("«رضا» در گروه ب فیلتر است",
          nf.match_name(CHAT_B, reza) == "رضا")
    check("«رضا» در گروه الف فیلتر نیست",
          nf.match_name(CHAT_A, reza) is None)

    send(bot, CHAT_A, owner, "لغو اسم حسین")
    check("حذف در گروه الف روی گروه ب اثر ندارد",
          nf.list_terms(CHAT_B) == ["رضا"])


def test_edge_cases_and_persistence():
    print("\n### 🧯 ورودی نامعتبر و ماندگاری")
    temp = use_temp_files()
    bot = Bot()
    owner = User(OWNER_ID, "مالک")

    bare, consumed = send(bot, CHAT_A, owner, "فیلتر اسم")
    check("دستور بدون عبارت رد شد",
          consumed is True and bare.said("بعد از دستور"))
    check("چیزی ثبت نشد", nf.list_terms(CHAT_A) == [])

    only_marks, _c = send(bot, CHAT_A, owner, "فیلتر اسم ...")
    check("عبارت فقط‌علامت ثبت نشد", nf.list_terms(CHAT_A) == [],
          f"-> {nf.list_terms(CHAT_A)}")

    long_term, _c = send(bot, CHAT_A, owner,
                         "فیلتر اسم " + "ا" * (nf.MAX_TERM_LENGTH + 5))
    check("عبارت خیلی طولانی رد شد",
          long_term.said("طولانی") and nf.list_terms(CHAT_A) == [])

    send(bot, CHAT_A, owner, "فیلتر اسم حسین")
    nf.FILE = temp / "name_filters.json"
    nf.reset_cache()
    check("بعد از ری‌استارت فیلتر باقی ماند",
          nf.list_terms(CHAT_A) == ["حسین"])
    check("بعد از ری‌استارت تطبیق کار می‌کند",
          nf.match_name(CHAT_A, User(1, "حسین")) == "حسین")
    raw = json.loads((temp / "name_filters.json").read_text(encoding="utf-8"))
    check("فایل JSON معتبر است", isinstance(raw, dict) and raw)


def test_help_section():
    print("\n### 📖 بخش راهنمای لیست ادمینی")
    section, spans = nf.build_help_section()
    lines = section.splitlines()
    check("خط اول درست است",
          lines[0] == "برای فیلتر اسم یک کاربر", f"-> {lines[0]!r}")
    check("خط دوم درست است",
          lines[1] == "بنویسید فیلتر اسم بعد نام را بنویسید")
    check("خط سوم درست است", lines[2] == "برای لغو بنویسید")
    check("خط چهارم درست است", lines[3] == "لغو اسم بعد اسم را بنویسید")
    check("بین جمله‌ها خط خالی نیست",
          "\n\n" not in section and len(lines) == 4)
    check("کل متن Bold است", ("bold", 0, nf.u16_len(section)) in spans)
    check("کل متن داخل نقل‌قول است",
          ("blockquote", 0, nf.u16_len(section)) in spans)

    source = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8")
    check("به راهنمای لیست ادمینی وصل شده است",
          "NAME_FILTER_HELP_SECTION" in source)
    check("هم در متن، هم Bold، هم Quote ثبت شده است",
          source.count("NAME_FILTER_HELP_SECTION") >= 4,
          f"-> {source.count('NAME_FILTER_HELP_SECTION')}")


def main():
    print("=" * 60)
    print("🚫 تست قابلیت فیلتر اسم")
    print("=" * 60)
    test_command_matching()
    test_dispatch_lane()
    test_add_and_remove_text()
    test_remove_only_one()
    test_emoji()
    test_list_command()
    test_matching_uses_existing_normalization()
    test_detector_integration()
    test_first_message_enforcement()
    test_permissions()
    test_group_isolation()
    test_edge_cases_and_persistence()
    test_help_section()
    print("\n" + "=" * 60)
    print(f"PASSED={PASSED}  FAILED={FAILED}")
    print("=" * 60)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
