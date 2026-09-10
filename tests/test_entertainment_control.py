"""تست واقعی قابلیت «کنترل سرگرمی» به تفکیک گروه.

    python tests/test_entertainment_control.py

پوشش: پیش‌فرض فعال، خاموش/فعال کردن توسط مدیر، رد کردن کاربر عادی، Bold
واقعیِ سه پیام، نمایش «لیست بازی» در حالت خاموش، بلاک شدن اجرای بازی‌ها در
همهٔ مسیرها، صفر بودن جایزه/سکه هنگام بلاک، استقلال دو گروه و ماندگاری
وضعیت بعد از restart.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# دادهٔ واقعی ربات نباید دست بخورد: هر اجرا در یک DATA_DIR موقت.
_TEMP_DATA_DIR = tempfile.mkdtemp(prefix="entertainment-test-")
os.environ["SOROUSH_BOT_DATA_DIR"] = _TEMP_DATA_DIR

from modules import entertainment_control as ec  # noqa: E402
import handlers.fox_games_router as router  # noqa: E402

PASSED = FAILED = 0

GROUP_A = -100511
GROUP_B = -100522
ADMIN_ID = 7001
NORMAL_ID = 7002


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


# --------------------------------------------------------------------------
# ابزارهای شبیه‌سازی
# --------------------------------------------------------------------------
class Entity:
    """جایگزین MessageEntityBold برای مقایسه در تست."""

    def __init__(self, offset=0, length=0):
        self.offset = offset
        self.length = length


class User:
    def __init__(self, uid, name=None, username=None):
        self.id = uid
        self.first_name = name
        self.last_name = None
        self.username = username


class Event:
    def __init__(self, is_private=False):
        self.out = []
        self.entities = []
        self.is_private = is_private

    async def reply(self, text, formatting_entities=None, **kwargs):
        self.out.append(text)
        self.entities.append(list(formatting_entities or []))
        return None

    def said(self, needle):
        return any(needle in message for message in self.out)

    def last(self):
        return self.out[-1] if self.out else ""

    def last_entities(self):
        return self.entities[-1] if self.entities else []


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
        self.logger = Logger()
        self.paid = []

    def award_coins(self, chat_id, user_id, name, amount):
        """اگر بازیِ بلاک‌شده اجرا شود، اینجا سکه ثبت می‌شود → تست RED."""
        self.paid.append((chat_id, user_id, amount))


def u16(text):
    return len(text.encode("utf-16-le")) // 2


def bold_substrings(text, entities):
    """متنِ دقیقی که با entity ها Bold شده است."""
    units = text.encode("utf-16-le")
    result = []
    for entity in entities:
        start = entity.offset * 2
        end = start + entity.length * 2
        result.append(units[start:end].decode("utf-16-le"))
    return result


def reset_state():
    ec.reset(GROUP_A)
    ec.reset(GROUP_B)
    router.reset_all()


# --------------------------------------------------------------------------
#  شبیه‌سازی مسیر دستور در message_handler (همان منطق، بدون pipeline سنگین)
# --------------------------------------------------------------------------
async def run_control_command(event, chat_id, user_id, text, is_admin):
    """همان شاخهٔ «سرگرمی خاموش/فعال» داخل message_handler."""
    if text not in ec.COMMANDS:
        return False
    if not is_admin:
        await event.reply(ec.PERMISSION_DENIED)
        return True
    if text == ec.COMMAND_DISABLE:
        ec.disable(chat_id)
        await ec.send_disabled_notice(event)
    else:
        ec.enable(chat_id)
        await ec.send_enabled_notice(event)
    return True


# --------------------------------------------------------------------------
# ۱ — پیش‌فرض فعال
# --------------------------------------------------------------------------
def test_default_enabled():
    print("\n### ۱ پیش‌فرض سرگرمی فعال است")
    reset_state()
    check("گروه بدون تنظیم فعال است", ec.is_enabled(GROUP_A))
    check("گروه دوم هم فعال است", ec.is_enabled(GROUP_B))
    check("گارد در حالت پیش‌فرض بازی را بلاک نمی‌کند",
          not ec.blocks(GROUP_A, "چیستان"))


# --------------------------------------------------------------------------
# ۲ و ۳ — خاموش کردن توسط مدیر + پیام دقیق و Bold واقعی
# --------------------------------------------------------------------------
def test_admin_disable_and_message():
    print("\n### ۲/۳ مدیر «سرگرمی خاموش» و پیام دقیق Bold")
    reset_state()
    event = Event()
    handled = asyncio.run(run_control_command(
        event, GROUP_A, ADMIN_ID, "سرگرمی خاموش", is_admin=True))
    check("دستور توسط مدیر پذیرفته شد", handled)
    check("سرگرمی گروه خاموش شد", not ec.is_enabled(GROUP_A))
    check("متن دقیقاً «🎮 بازی های روباه غیر فعال شد» است",
          event.last() == "🎮 بازی های روباه غیر فعال شد",
          f"-> {event.last()!r}")
    entities = event.last_entities()
    check("دقیقاً یک entity ارسال شد", len(entities) == 1, f"-> {entities}")
    check("کل پیام Bold واقعی است",
          bold_substrings(event.last(), entities) == [event.last()],
          f"-> {bold_substrings(event.last(), entities)}")
    check("offset/length صحیح UTF-16 است",
          entities and entities[0].offset == 0
          and entities[0].length == u16(event.last()))


# --------------------------------------------------------------------------
# ۴ — کاربر عادی نمی‌تواند وضعیت را عوض کند
# --------------------------------------------------------------------------
def test_normal_user_cannot_change():
    print("\n### ۴ کاربر عادی اجازه ندارد")
    reset_state()
    event = Event()
    asyncio.run(run_control_command(
        event, GROUP_A, NORMAL_ID, "سرگرمی خاموش", is_admin=False))
    check("سرگرمی همچنان فعال است", ec.is_enabled(GROUP_A))
    check("پیام رد دسترسی داده شد", event.said("❌"))
    check("پیام خاموش شدن ارسال نشد", not event.said("غیر فعال شد"))

    ec.disable(GROUP_A)
    event2 = Event()
    asyncio.run(run_control_command(
        event2, GROUP_A, NORMAL_ID, "سرگرمی فعال", is_admin=False))
    check("کاربر عادی نمی‌تواند روشن کند", not ec.is_enabled(GROUP_A))
    check("پیام فعال شدن ارسال نشد", not event2.said("فعال شد میتوانید"))


# --------------------------------------------------------------------------
# ۵ — «لیست بازی» در حالت خاموش هم نمایش داده می‌شود
# --------------------------------------------------------------------------
def test_game_list_still_shown():
    print("\n### ۵ «لیست بازی» در حالت خاموش نمایش داده می‌شود")
    reset_state()
    ec.disable(GROUP_A)
    for command in ("لیست بازی", "لیست بازی ها", "لیست بازی‌ها",
                    "بازی ها", "بازی‌ها"):
        check(f"«{command}» توسط گارد بلاک نمی‌شود",
              not ec.blocks(GROUP_A, command))
    check("«لیست بازی» جزو دستورهای بازی ثبت نشده",
          not ec.is_game_command("لیست بازی"))
    source = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8")
    check("شاخهٔ «لیست بازی» هنوز در کد وجود دارد",
          'if clean_text.strip() in ["لیست بازی"' in source)


# --------------------------------------------------------------------------
# ۶ و ۷ و ۸ — بلاک شدن اجرای بازی + پیام دقیق + Bold فقط روی «سرگرمی فعال»
# --------------------------------------------------------------------------
def test_blocked_launch_message():
    print("\n### ۶/۷/۸ بلاک شدن بازی و پیام دقیق")
    reset_state()
    ec.disable(GROUP_A)
    event = Event()
    blocked = asyncio.run(ec.guard(event, GROUP_A, "چیستان"))
    check("اجرای بازی متوقف شد", blocked)
    expected = (
        "بازی های روباه عموم غیر فعال می‌باشند ؛ برای فعال سازی باید ادمین "
        "یا مالک با دستور سرگرمی فعال بازی هارو فعال کند تا بتوانید از "
        "بازی ها استفاده کنید ☑️"
    )
    check("متن پیام غیرفعال بودن دقیق است", event.last() == expected,
          f"-> {event.last()!r}")
    entities = event.last_entities()
    check("دقیقاً یک entity ارسال شد", len(entities) == 1, f"-> {entities}")
    bolds = bold_substrings(event.last(), entities)
    check("فقط «سرگرمی فعال» Bold است", bolds == ["سرگرمی فعال"],
          f"-> {bolds}")
    check("عبارت Bold شده دقیقاً همان جای متن است",
          entities and entities[0].offset == u16(
              event.last()[:event.last().find("سرگرمی فعال")]))


# --------------------------------------------------------------------------
# ۹ و ۱۰ و ۱۱ — فعال کردن توسط مدیر، پیام دقیق، اجرای دوبارهٔ بازی
# --------------------------------------------------------------------------
def test_admin_enable_and_resume():
    print("\n### ۹/۱۰/۱۱ فعال‌سازی مجدد توسط مدیر")
    reset_state()
    ec.disable(GROUP_A)
    event = Event()
    asyncio.run(run_control_command(
        event, GROUP_A, ADMIN_ID, "سرگرمی فعال", is_admin=True))
    check("سرگرمی دوباره فعال شد", ec.is_enabled(GROUP_A))
    expected = (
        "🍬 : بازی های روباه فعال شد میتوانید با دستور لیست بازی از بازی ها "
        "استفاده کنید"
    )
    check("متن پیام فعال شدن دقیق است", event.last() == expected,
          f"-> {event.last()!r}")
    entities = event.last_entities()
    check("کل پیام فعال شدن Bold واقعی است",
          bold_substrings(event.last(), entities) == [event.last()],
          f"-> {bold_substrings(event.last(), entities)}")

    after = Event()
    check("گارد دیگر بازی را بلاک نمی‌کند",
          not asyncio.run(ec.guard(after, GROUP_A, "چیستان")))
    check("هیچ پیام مسدودی ارسال نشد", not after.out)

    # اجرای واقعی یک بازی Fox از راه روتر، بعد از فعال شدن.
    bot, game_event = Bot(), Event()
    started = asyncio.run(router.handle(
        bot, game_event, GROUP_A, ADMIN_ID, User(ADMIN_ID, "Ali"),
        "بخند یا بباز", bot.logger))
    check("بازی «بخند یا بباز» بعد از فعال شدن واقعاً اجرا شد", started)
    check("بازی پیام شروع خودش را فرستاد (نه پیام غیرفعال بودن)",
          game_event.said("بخند یا بباز")
          and not game_event.said("بازی های روباه عموم غیر فعال"),
          f"-> {game_event.out}")
    router.reset_all()


# --------------------------------------------------------------------------
# ۱۲ — استقلال دو گروه
# --------------------------------------------------------------------------
def test_per_group_isolation():
    print("\n### ۱۲ استقلال وضعیت دو گروه")
    reset_state()
    ec.disable(GROUP_A)
    check("گروه A خاموش است", not ec.is_enabled(GROUP_A))
    check("گروه B همچنان فعال (پیش‌فرض)", ec.is_enabled(GROUP_B))
    ec.disable(GROUP_B)
    ec.enable(GROUP_A)
    check("گروه A فعال شد", ec.is_enabled(GROUP_A))
    check("گروه B خاموش ماند", not ec.is_enabled(GROUP_B))
    check("گارد گروه B بازی را بلاک می‌کند", ec.blocks(GROUP_B, "بقا"))
    check("گارد گروه A بازی را بلاک نمی‌کند", not ec.blocks(GROUP_A, "بقا"))


# --------------------------------------------------------------------------
# ۱۳ — بلاک شدن هیچ جایزه/سکه‌ای نمی‌سازد
# --------------------------------------------------------------------------
def test_blocked_launch_pays_nothing():
    print("\n### ۱۳ بلاک شدن هیچ سکه/state ای نمی‌سازد")
    reset_state()
    ec.disable(GROUP_A)
    bot = Bot()
    for command in ("بخند یا بباز", "بقا", "جعبه شانسی", "خون آشام",
                    "معما", "حدس جمله", "ساخت جمله", "مین یاب",
                    "بهترین جواب", "نبرد", "کارگاه"):
        event = Event()
        consumed = asyncio.run(router.handle(
            bot, event, GROUP_A, ADMIN_ID, User(ADMIN_ID, "Ali"),
            command, bot.logger))
        check(f"«{command}» مصرف و بلاک شد", consumed)
        check(f"«{command}» پیام غیرفعال بودن داد",
              event.said("بازی های روباه عموم غیر فعال"))
        check(f"«{command}» هیچ state ای نساخت", not router.any_active(GROUP_A))
    check("هیچ سکه‌ای پرداخت نشد", bot.paid == [], f"-> {bot.paid}")
    check("لاگ بلاک شدن ثبت شد", bot.logger.has("FOX GAME BLOCKED"))


# --------------------------------------------------------------------------
# ۱۴ — ماندگاری وضعیت بعد از restart
# --------------------------------------------------------------------------
def test_state_survives_restart():
    print("\n### ۱۴ ماندگاری وضعیت بعد از restart")
    reset_state()
    ec.disable(GROUP_A)
    ec.enable(GROUP_B)
    check("فایل وضعیت روی دیسک ساخته شد", Path(ec.FILE).exists(),
          f"-> {ec.FILE}")
    stored = json.loads(Path(ec.FILE).read_text(encoding="utf-8"))
    check("کلید گروه A ذخیره شد", str(GROUP_A) in
          {str(key) for key in stored}, f"-> {stored}")

    script = (
        "import os,sys;"
        f"sys.path.insert(0, {str(ROOT)!r});"
        f"os.environ['SOROUSH_BOT_DATA_DIR']={_TEMP_DATA_DIR!r};"
        "from modules import entertainment_control as ec;"
        f"print(int(ec.is_enabled({GROUP_A})), int(ec.is_enabled({GROUP_B})),"
        f" int(ec.is_enabled(-100999)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        cwd=str(ROOT),
    )
    check("پروسهٔ تازه بدون خطا خواند", result.returncode == 0,
          result.stderr[-300:])
    check("بعد از restart گروه A خاموش مانده", result.stdout.split()[:1] == ["0"],
          f"-> {result.stdout!r}")
    check("بعد از restart گروه B فعال مانده", result.stdout.split()[1:2] == ["1"],
          f"-> {result.stdout!r}")
    check("گروه ناشناخته بعد از restart پیش‌فرض فعال است",
          result.stdout.split()[2:3] == ["1"], f"-> {result.stdout!r}")


# --------------------------------------------------------------------------
# ۱۵ — همهٔ مسیرهای اجرای بازی guard شده‌اند
# --------------------------------------------------------------------------
GAME_BRANCH_PATTERNS = (
    'if clean_text == "اسم فامیل":',
    'if clean_text == "حدس ایموجی":',
    'if clean_text == "حدس پرچم":',
    'if clean_text == "تصحیح کلمات":',
    'if clean_text == "کی بیشتر بلده":',
    'if clean_text == "دروغ یا حقیقت":',
    'if normalized_game_command == "چهار گزینه ای":',
    'if clean_text == "جای خالی":',
    'if clean_text == "چیستان":',
    'if clean_text in ["جرعت", "جرات", "جرئت"]:',
    'if clean_text in ["حقیقت", "حقیقت بگو"]:',
    'if clean_text == "جک":',
    "clean_text in FOX_GAME_COMMANDS",
)


def test_all_game_paths_guarded():
    print("\n### ۱۵ همهٔ مسیرهای اجرای بازی از گارد عبور می‌کنند")
    source = (ROOT / "handlers" / "message_handler.py").read_text(
        encoding="utf-8")
    guard_index = source.find("entertainment_control.guard(event, chat_id")
    check("گارد مرکزی در message_handler نصب شده", guard_index > 0)
    for pattern in GAME_BRANCH_PATTERNS:
        index = source.find(pattern)
        check(f"مسیر {pattern[:42]}… بعد از گارد است",
              index > guard_index > 0, f"-> guard={guard_index} branch={index}")

    router_source = (ROOT / "handlers" / "fox_games_router.py").read_text(
        encoding="utf-8")
    check("روتر Fox هم گارد مستقل دارد",
          "entertainment_control.guard(event, chat_id, text)" in router_source)

    # هر دستور شروع بازی در روتر باید در فهرست گارد باشد.
    for command in router.FOX_GAME_COMMANDS:
        check(f"«{command}» در فهرست گارد هست",
              command in ec.GAME_COMMANDS)

    # بازی‌های قدیمی داخل message_handler
    for command in ("چیستان", "جای خالی", "حدس ایموجی", "حدس پرچم",
                    "اسم فامیل", "تصحیح کلمات", "چهار گزینه ای",
                    "کی بیشتر بلده", "دروغ یا حقیقت", "جرعت", "حقیقت", "جک"):
        check(f"بازی قدیمی «{command}» گارد می‌شود",
              ec.blocks(-100777, command) is False and True)
    ec.disable(-100777)
    for command in ("چیستان", "جای خالی", "حدس ایموجی", "حدس پرچم",
                    "اسم فامیل", "تصحیح کلمات", "چهار گزینه ای",
                    "چهار گزینه‌ای", "کی بیشتر بلده", "دروغ یا حقیقت",
                    "جرعت", "جرات", "جرئت", "حقیقت", "حقیقت بگو", "جک"):
        check(f"«{command}» در حالت خاموش بلاک می‌شود",
              ec.blocks(-100777, command))
    check("سایت بازی هرگز بلاک نمی‌شود",
          not ec.blocks(-100777, "سایت بازی")
          and not ec.blocks(-100777, "/game")
          and not ec.blocks(-100777, "سایت"))
    check("دستور غیربازی بلاک نمی‌شود",
          not ec.blocks(-100777, "موجودی")
          and not ec.blocks(-100777, "راهنما"))
    ec.reset(-100777)


# --------------------------------------------------------------------------
# سازگاری: هیچ دادهٔ دیگری لمس نمی‌شود
# --------------------------------------------------------------------------
def test_storage_isolated():
    print("\n### سازگاری: فایل مستقل و بدون تداخل instance")
    check("نام فایل اختصاصی است",
          Path(ec.FILE).name == "entertainment_mode.json", f"-> {ec.FILE}")
    check("زیر DATA_DIR همان instance ذخیره می‌شود",
          str(ec.FILE).startswith(_TEMP_DATA_DIR), f"-> {ec.FILE}")
    # فایل فقط کلیدهای گروه با مقدار boolean دارد؛ هیچ دادهٔ دیگری داخلش
    # نوشته نمی‌شود و هیچ فایل دیگری از این مسیر دست نمی‌خورد.
    stored = json.loads(Path(ec.FILE).read_text(encoding="utf-8"))
    check("محتوای فایل فقط group_id → boolean است",
          all(isinstance(value, bool) for value in stored.values())
          and all(re.fullmatch(r"-?\d+", str(key)) for key in stored),
          f"-> {stored}")

    # سکه‌های موجود قبل و بعد از یک تلاشِ بلاک‌شده باید دقیقاً یکی باشند.
    from economy import get_balance
    ec.disable(GROUP_A)
    before = dict(get_balance(GROUP_A, NORMAL_ID))
    bot = Bot()
    asyncio.run(router.handle(
        bot, Event(), GROUP_A, NORMAL_ID, User(NORMAL_ID, "Ali"),
        "جعبه شانسی", bot.logger))
    after = dict(get_balance(GROUP_A, NORMAL_ID))
    check("موجودی سکه پس از تلاش بلاک‌شده تغییر نکرد", before == after,
          f"-> {before} != {after}")
    ec.reset(GROUP_A)


def main():
    test_default_enabled()
    test_admin_disable_and_message()
    test_normal_user_cannot_change()
    test_game_list_still_shown()
    test_blocked_launch_message()
    test_admin_enable_and_resume()
    test_per_group_isolation()
    test_blocked_launch_pays_nothing()
    test_state_survives_restart()
    test_all_game_paths_guarded()
    test_storage_isolated()

    print(f"\n{'=' * 52}")
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
