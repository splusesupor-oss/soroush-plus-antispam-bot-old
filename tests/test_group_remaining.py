"""⏳ «مهلت گروه» + همگام‌سازی «لیست انقضا» — تست کامل و مستقل.

پوشش:
    • تطبیق دقیق دستور «مهلت گروه» و نبود تداخل با دستورهای دیگر
    • خروجی دقیق سه‌خطی؛ فقط «گروه» و «مهلت باقی مانده» Bold؛ بدون
      نقل‌قول شیشه‌ای
    • مهلت باقی‌مانده از تاریخ انقضای «واقعی» محاسبه می‌شود
    • دسترسی: مالک اصلی ربات، مالک گروه و ادمین ثبت‌شده؛ بقیه نه
    • با تغییر نام گروه، اولین پیام نام جدید را ذخیره می‌کند و گروه با
      ID شناخته می‌شود (نه اسم)
    • پس از انقضا رفتار مسدودسازی قبلی دست‌نخورده می‌ماند
    • پس از تمدید، لیست انقضا وضعیت/تاریخ جدید نشان می‌دهد
    • همگام‌سازی دوره‌ای (۲۴ساعته) فقط دادهٔ گزارش را تمیز می‌کند و
      هیچ گروه زنده‌ای را حذف نمی‌کند

    python tests/test_group_remaining.py
"""
import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import handlers.group_expiry_handler as geh
import modules.admin_storage as admin_storage
import modules.group_expiry as ge
import modules.group_storage as gs
import modules.owner_check as oc
from modules.expiry_report import (
    build_group_list,
    build_report,
    sync_expiry_list,
)
from modules.group_dispatch import LANE_ADMIN, classify_priority

PASSED = FAILED = 0
CHAT = -1001234567890
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


class User:
    def __init__(self, uid, name="U", username=None):
        self.id = uid
        self.first_name = name
        self.last_name = None
        self.username = username


class Chat:
    def __init__(self, title="گروه تست"):
        self.title = title
        self.id = CHAT


class Event:
    def __init__(self, title="گروه تست"):
        self.out = []
        self.entities = []
        self.is_private = False
        self._chat = Chat(title)

    async def reply(self, text, formatting_entities=None, **kwargs):
        self.out.append(text)
        self.entities.append(formatting_entities or [])
        return None

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


def _utcnow():
    return datetime.now(timezone.utc)


def use_temp_files():
    """هر تست روی فایل‌های تازهٔ خودش کار می کند."""
    temp = Path(tempfile.mkdtemp())

    ge.FILE = temp / "group_expiry.json"
    ge._cache = None
    ge._cache_mtime = None

    gs.FILE = temp / "groups.json"
    gs._cache = None
    gs._cache_mtime = None

    admin_storage.FILE = temp / "admins.json"
    admin_storage._cache = None
    admin_storage._cache_mtime = None

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


# ===========================================================================
# تطبیق دستور
# ===========================================================================
def test_command_matching():
    print("\n### 🎯 تطبیق دقیق «مهلت گروه»")
    check("«مهلت گروه» تطبیق می‌کند",
          ge.match_remaining_command("مهلت گروه") == "مهلت گروه")
    check("نیم‌فاصله پذیرفته می‌شود",
          ge.match_remaining_command("مهلت\u200cگروه") == "مهلت گروه")
    check("فاصلهٔ اضافه پذیرفته می‌شود",
          ge.match_remaining_command("  مهلت    گروه  ") == "مهلت گروه")

    for other in (
        "مهلت گروه من", "گروه مهلت", "مهلت", "گروه", "ثبت مهلت گروه",
        "مهلت گروه را ببین", "۵ روز", "یک هفته", "دو هفته", "یک ماه",
        "لیست انقضا", "فعال", "قفل", "راهنما",
    ):
        check(f"«{other}» تطبیق نمی‌کند",
              ge.match_remaining_command(other) is None,
              f"-> {ge.match_remaining_command(other)!r}")

    # دستورهای ثبت مهلت نباید با دستور خبری اشتباه گرفته شوند
    check("دستورهای ثبت مهلت همچنان جدا هستند",
          ge.match_command("مهلت گروه") is None)
    check("دستور خبری، ثبت مهلت نیست",
          all(ge.match_remaining_command(c) is None
              for c in ("۵ روز", "یک هفته", "دو هفته", "یک ماه")))


# ===========================================================================
# قالب‌بندی مدت و پیام
# ===========================================================================
def test_format_remaining():
    print("\n### 🕰️ قالب‌بندی مدت باقی‌مانده")
    check("بدون رکورد → ثبت نشده",
          ge.format_remaining(None) == "ثبت نشده")
    check("صفر → منقضی شده", ge.format_remaining(0) == "منقضی شده")
    check("منفی → منقضی شده", ge.format_remaining(-5) == "منقضی شده")
    check("روز و ساعت",
          ge.format_remaining(2 * 86400 + 3 * 3600 + 900) == "۲ روز و ۳ ساعت")
    # قرارداد نمایش با «لیست انقضا» یکسان است: وقتی ساعت وجود دارد دقیقه
    # نمایش داده نمی‌شود.
    check("فقط ساعت",
          ge.format_remaining(5 * 3600 + 12 * 60) == "۵ ساعت")
    check("فقط دقیقه", ge.format_remaining(7 * 60) == "۷ دقیقه")
    check("زیر یک دقیقه", ge.format_remaining(30) == "کمتر از ۱ دقیقه")
    check("ارقام فارسی هستند",
          all(ch not in ge.format_remaining(90061) for ch in "0123456789"))


def test_remaining_message_format():
    print("\n### 📄 خروجی دقیق سه‌خطی")
    text, spans = ge.build_remaining_message("گروه من", "۲ روز و ۳ ساعت")
    lines = text.split("\n")
    check("دقیقاً سه خط است", len(lines) == 3, f"-> {lines}")
    check("خط اول درست است", lines[0] == "↻- گروه : گروه من",
          f"-> {lines[0]!r}")
    check("خط دوم درست است", lines[1] == "مهلت باقی مانده : ۲ روز و ۳ ساعت",
          f"-> {lines[1]!r}")
    check("خط تمدید درست است",
          lines[2] == "برای تمدید اشتراک : 𝄞 @aifox_bot",
          f"-> {lines[2]!r}")

    check("دقیقاً دو اسپن وجود دارد", len(spans) == 2, f"-> {spans}")
    check("هیچ نقل‌قول شیشه‌ای نیست",
          all(kind != "blockquote" for kind, *_ in spans))
    bold_texts = {decode_span(text, off, ln)
                  for kind, off, ln in spans if kind == "bold"}
    check("فقط «گروه» و «مهلت باقی مانده» بولد هستند",
          bold_texts == {"گروه", "مهلت باقی مانده"}, f"-> {bold_texts}")
    check("نام گروه بولد نیست", "گروه من" not in bold_texts)
    check("مدت بولد نیست", "۲ روز و ۳ ساعت" not in bold_texts)

    # آفست‌ها روی مرز واحدهای UTF-16 درست‌اند (𝄞 جفت جایانش دارد)
    total = len(text.encode("utf-16-le")) // 2
    check("اسپن‌ها داخل متن هستند",
          all(0 <= off and off + ln <= total for _, off, ln in spans))

    # حتی اگر نام گروه خودش کلمهٔ برچسب را داشته باشد، برچسبِ خط دوم
    # بولد می‌شود نه کلمهٔ داخل نام گروه در خط اول.
    tricky, spans2 = ge.build_remaining_message("مهلت باقی مانده", "۱ روز")
    expected_off = len(tricky.split("\n")[0].encode("utf-16-le")) // 2 + 1
    label_offsets = [
        off for kind, off, ln in spans2
        if kind == "bold"
        and decode_span(tricky, off, ln) == "مهلت باقی مانده"
    ]
    check("در نام تکراری، برچسبِ خط دوم بولد می‌شود",
          label_offsets == [expected_off], f"-> {label_offsets}")


# ===========================================================================
# هندلر — پاسخ واقعی از تاریخ انقضای واقعی
# ===========================================================================
def _run(coro):
    return asyncio.run(coro)


def test_handler_shows_real_remaining():
    print("\n### 📋 مهلت باقی‌مانده از تاریخ واقعی")
    use_temp_files()
    gs.activate_group(CHAT, "گروه تست")
    ge.set_expiry(CHAT, ge.FIVE_DAYS, title="گروه تست",
                  now=_utcnow() - timedelta(days=2, hours=20, minutes=30,
                                             seconds=20))
    event = Event()
    handled = _run(geh.handle_remaining(
        Bot(), event, CHAT, User(OWNER_ID), "مهلت گروه"))
    check("پیام مصرف شد", handled is True)
    check("پاسخ ارسال شد", len(event.out) == 1, f"-> {event.out}")
    text = event.out[0] if event.out else ""
    check("مهلت واقعی ≈ ۲ روز و ۳ ساعت نمایش داده می‌شود",
          "مهلت باقی مانده : ۲ روز و ۳ ساعت" in text, f"-> {text!r}")
    check("نام گروه در خروجی است", "↻- گروه : گروه تست" in text)
    check("خط تمدید در خروجی است",
          "برای تمدید اشتراک : 𝄞 @aifox_bot" in text)


def test_handler_expired_group():
    print("\n### 📋 گروه منقضی‌شده")
    use_temp_files()
    gs.activate_group(CHAT, "گروه تست")
    gs.set_group_owner(CHAT, GROUP_OWNER_ID)
    ge.set_expiry(CHAT, ge.FIVE_DAYS, title="گروه تست",
                  now=_utcnow() - timedelta(days=9))
    event = Event()
    _run(geh.handle_remaining(Bot(), event, CHAT, User(GROUP_OWNER_ID),
                              "مهلت گروه"))
    check("وضعیت «منقضی شده» نمایش داده می‌شود",
          event.said("مهلت باقی مانده : منقضی شده"), f"-> {event.out}")


def test_handler_no_record():
    print("\n### 📋 گروه بدون تاریخ انقضا")
    use_temp_files()
    gs.activate_group(CHAT, "گروه تست")
    gs.set_group_owner(CHAT, GROUP_OWNER_ID)
    event = Event()
    _run(geh.handle_remaining(Bot(), event, CHAT, User(GROUP_OWNER_ID),
                              "مهلت گروه"))
    check("وضعیت «ثبت نشده» نمایش داده می‌شود",
          event.said("مهلت باقی مانده : ثبت نشده"), f"-> {event.out}")


def test_handler_permissions():
    print("\n### 🔐 دسترسی: فقط مالک/ادمین گروه")
    use_temp_files()
    gs.activate_group(CHAT, "گروه تست")
    gs.set_group_owner(CHAT, GROUP_OWNER_ID)
    admin_storage.add_admin(CHAT, ADMIN_ID, "admin_test")
    ge.set_expiry(CHAT, ge.ONE_WEEK, title="گروه تست")

    # مالک اصلی ربات
    ev1 = Event()
    _run(geh.handle_remaining(Bot(), ev1, CHAT, User(OWNER_ID), "مهلت گروه"))
    check("مالک اصلی ربات پاسخ می‌گیرد", ev1.said("↻- گروه :"),
          f"-> {ev1.out}")

    # مالک گروه
    ev2 = Event()
    _run(geh.handle_remaining(Bot(), ev2, CHAT, User(GROUP_OWNER_ID),
                              "مهلت گروه"))
    check("مالک گروه پاسخ می‌گیرد", ev2.said("↻- گروه :"), f"-> {ev2.out}")

    # ادمین ثبت‌شده
    ev3 = Event()
    _run(geh.handle_remaining(Bot(), ev3, CHAT, User(ADMIN_ID), "مهلت گروه"))
    check("ادمین ثبت‌شده پاسخ می‌گیرد", ev3.said("↻- گروه :"),
          f"-> {ev3.out}")

    # کاربر عادی
    ev4 = Event()
    _run(geh.handle_remaining(Bot(), ev4, CHAT, User(STRANGER_ID),
                              "مهلت گروه"))
    check("کاربر عادی مهلت را نمی‌بیند", not ev4.said("↻- گروه :"),
          f"-> {ev4.out}")
    check("کاربر عادی پیام دسترسی می‌گیرد",
          ev4.said("فقط مالک یا ادمین گروه"), f"-> {ev4.out}")


def test_handler_updates_title_after_rename():
    print("\n### 🔄 تغییر نام گروه با اولین پیام به‌روز می‌شود")
    use_temp_files()
    gs.activate_group(CHAT, "نام قدیمی گروه")
    ge.set_expiry(CHAT, ge.ONE_WEEK, title="نام قدیمی گروه")

    event = Event(title="نام جدید گروه")
    _run(geh.handle_remaining(Bot(), event, CHAT, User(OWNER_ID),
                              "مهلت گروه"))
    check("پاسخ با نام جدید است", event.said("↻- گروه : نام جدید گروه"),
          f"-> {event.out}")
    groups = json.loads(gs.FILE.read_text(encoding="utf-8"))
    check("نام جدید در groups.json ذخیره شد",
          any(g.get("title") == "نام جدید گروه" for g in groups.values()))
    record = ge.get_record(CHAT)
    check("نام جدید در رکورد انقضا هم ذخیره شد",
          record.get("title") == "نام جدید گروه", f"-> {record}")
    check("تاریخ انقضا دست نخورد",
          ge.get_record(CHAT).get("days") == 7)


def test_group_identity_is_by_id():
    print("\n### 🆔 گروه با ID شناخته می‌شود، نه اسم")
    use_temp_files()
    gs.activate_group(CHAT, "گروه تست")
    ge.set_expiry(CHAT, ge.ONE_MONTH, title="گروه تست")

    # شکل‌های مختلف شناسه باید یک رکورد باشند
    check("شکل -100 و کوتاه یک رکوردند",
          ge.expires_at(-1001234567890) == ge.expires_at(1234567890))
    check("شکل منفی ساده هم یک رکورد است",
          ge.expires_at(-1234567890) == ge.expires_at(1234567890))

    # تغییر نام نباید رکورد جدید بسازد
    ge.update_title(CHAT, "اسم کاملاً متفاوت")
    check("بعد از تغییر نام هنوز یک رکورد وجود دارد",
          len(ge.all_records()) == 1)
    check("تغییر نام، تاریخ انقضا را عوض نکرد",
          ge.get_record(CHAT)["days"] == 29)


def test_handler_ignores_other_text():
    print("\n### 🎯 هندلر متن‌های دیگر را مصرف نمی‌کند")
    use_temp_files()
    event = Event()
    for text in ("مهلت گروه من", "۵ روز", "راهنما", "لیست انقضا", ""):
        handled = _run(geh.handle_remaining(
            Bot(), event, CHAT, User(OWNER_ID), text))
        check(f"«{text}» مصرف نمی‌شود", handled is False)
    check("پاسخی ارسال نشد", event.out == [])


# ===========================================================================
# رفتار انقضای موجود دست‌نخورده می‌ماند
# ===========================================================================
def test_expiry_blocking_untouched():
    print("\n### ⛔ مسدودسازی پس از انقضا مثل قبل است")
    use_temp_files()
    gs.activate_group(CHAT, "گروه تست")
    ge.set_expiry(CHAT, ge.FIVE_DAYS, title="گروه تست",
                  now=_utcnow() - timedelta(days=6))
    check("گروه منقضی است", ge.is_expired(CHAT))
    check("کاربر عادی مسدود است", geh.blocks_message(CHAT, User(STRANGER_ID)))
    check("مالک اصلی عبور می‌کند",
          not geh.blocks_message(CHAT, User(OWNER_ID)))

    # تمدید دوباره همه‌چیز را باز می‌کند
    ge.set_expiry(CHAT, ge.ONE_WEEK, title="گروه تست")
    check("پس از تمدید دیگر منقضی نیست", not ge.is_expired(CHAT))
    check("پس از تمدید کاربر عادی آزاد است",
          not geh.blocks_message(CHAT, User(STRANGER_ID)))
    check("پرچم اعلام پس از تمدید پاک شد", not ge.was_notified(CHAT))


def test_update_title_is_safe():
    print("\n### 🖋️ به‌روزرسانی نام رکورد، بی‌خطر است")
    use_temp_files()
    check("برای گروه بدون رکورد، رکورد نمی‌سازد",
          ge.update_title(CHAT, "سلام") is False)
    check("رکوردی ساخته نشد", ge.all_records() == {})

    ge.set_expiry(CHAT, ge.ONE_WEEK, title="قدیم")
    before = ge.expires_at(CHAT)
    check("نام عوض می‌شود", ge.update_title(CHAT, "جدید") is True)
    check("نام تکراری تغییر محسوب نمی‌شود",
          ge.update_title(CHAT, "جدید") is False)
    check("نام خالی پذیرفته نمی‌شود", ge.update_title(CHAT, "  ") is False)
    check("تاریخ انقضا دست نخورد", ge.expires_at(CHAT) == before)
    check("پرچم اعلام دست نخورد", not ge.was_notified(CHAT))


# ===========================================================================
# لیست انقضا — هماهنگی با وضعیت واقعی + همگام‌سازی دوره‌ای
# ===========================================================================
def _mark_notified(key):
    assert ge.mark_notified(key), "mark_notified failed"


def test_sync_removes_finished_expired_only():
    print("\n### 🧹 همگام‌سازی فقط رکوردهای کاملاً تمام‌شده را پاک می‌کند")
    use_temp_files()
    past = _utcnow() - timedelta(days=30)
    # ۱) منقضی + اعلام‌شده + غیرفعال → باید حذف شود
    gs.activate_group(-1001111111111, "گروه تمام")
    gs.deactivate_group(-1001111111111, "گروه تمام")
    ge.set_expiry(-1001111111111, ge.ONE_WEEK, title="گروه تمام", now=past)
    _mark_notified("1111111111")

    # ۲) منقضی ولی اعلام‌نشده → ناظر هنوز کار دارد، می‌ماند
    gs.activate_group(-1002222222222, "گروه بی‌اعلام")
    gs.deactivate_group(-1002222222222, "گروه بی‌اعلام")
    ge.set_expiry(-1002222222222, ge.ONE_WEEK, title="گروه بی‌اعلام",
                  now=past)

    # ۳) منقضی + اعلام‌شده ولی گروه هنوز فعال → می‌ماند
    gs.activate_group(-1003333333333, "گروه فعال مانده")
    ge.set_expiry(-1003333333333, ge.ONE_WEEK, title="گروه فعال مانده",
                  now=past)
    _mark_notified("3333333333")

    # ۴) فعال با مهلت باقی‌مانده → هرگز حذف نمی‌شود
    gs.activate_group(-1004444444444, "گروه زنده")
    ge.set_expiry(-1004444444444, ge.ONE_MONTH, title="گروه زنده")

    summary = sync_expiry_list()
    check("دقیقاً یک رکورد حذف شد", summary["removed_expired"] == 1,
          f"-> {summary}")
    check("رکورد منقضی+اعلام‌شده+غیرفعال حذف شد",
          not ge.has_expiry(-1001111111111))
    check("رکورد اعلام‌نشده حفظ شد", ge.has_expiry(-1002222222222))
    check("رکورد گروه هنوزفعال حفظ شد", ge.has_expiry(-1003333333333))
    check("رکورد گروه زنده حفظ شد", ge.has_expiry(-1004444444444))

    # اجرای دوباره چیزی برای حذف ندارد
    again = sync_expiry_list()
    check("همگام‌سازی مجدد بی‌اثر است", again["removed_expired"] == 0)


def test_sync_refreshes_titles():
    print("\n### 🧹 همگام‌سازی نام‌ها را تازه می‌کند")
    use_temp_files()
    gs.activate_group(-1005555555555, "نام جدید")
    ge.set_expiry(-1005555555555, ge.ONE_MONTH, title="نام قدیم")

    summary = sync_expiry_list()
    check("یک نام به‌روز شد", summary["refreshed_titles"] == 1,
          f"-> {summary}")
    check("نام رکورد انقضا تازه شد",
          ge.get_record(-1005555555555).get("title") == "نام جدید")
    check("تاریخ انقضا دست نخورد",
          ge.get_record(-1005555555555)["days"] == 29)


def test_list_shows_live_status_after_renewal():
    print("\n### 📋 لیست انقضا بعد از تمدید وضعیت جدید نشان می‌دهد")
    use_temp_files()
    gs.activate_group(-1006666666666, "گروه تمدیدی")
    # اول منقضی می‌شود
    ge.set_expiry(-1006666666666, ge.FIVE_DAYS, title="گروه تمدیدی",
                  now=_utcnow() - timedelta(days=10))
    expired_list = build_group_list()
    check("قبل از تمدید «منقضی شده» دیده می‌شود",
          "منقضی شده" in expired_list, f"-> {expired_list!r}")

    # مالک تمدید می‌کند — لیست باید بلافاصله وضعیت تازه را نشان دهد
    ge.set_expiry(-1006666666666, ge.ONE_MONTH, title="گروه تمدیدی")
    renewed_list = build_group_list()
    check("بعد از تمدید دیگر «منقضی شده» نیست",
          "منقضی شده" not in renewed_list, f"-> {renewed_list!r}")
    check("بعد از تمدید مهلت جدید دیده می‌شود",
          "باقی مانده" in renewed_list, f"-> {renewed_list!r}")

    # گزارش کامل خصوصی هم وضعیت واقعی را نشان می‌دهد
    report = build_report()
    check("گزارش خصوصی هم تازه است", "منقضی شده" not in report
          and "گروه تمدیدی" in report, f"-> {report!r}")

    # گروه منقضی‌شده تا همگام‌سازی با وضعیت درست دیده می‌شود و بعد پاک
    gs.activate_group(-1007777777777, "گروه رفته")
    gs.deactivate_group(-1007777777777, "گروه رفته")
    ge.set_expiry(-1007777777777, ge.ONE_WEEK, title="گروه رفته",
                  now=_utcnow() - timedelta(days=9))
    _mark_notified("7777777777")
    before_sync = build_group_list()
    check("گروه منقضی قبل از همگام‌سازی با وضعیت درست دیده می‌شود",
          "گروه رفته" in before_sync and "منقضی شده" in before_sync,
          f"-> {before_sync!r}")
    sync_expiry_list()
    after_sync = build_group_list()
    check("گروه منقضی بعد از همگام‌سازی دیگر در لیست نمی‌ماند",
          "گروه رفته" not in after_sync, f"-> {after_sync!r}")


def test_sync_does_not_touch_expiry_enforcement():
    print("\n### 🛡️ همگام‌سازی فقط گزارش است، نه اجرای انقضا")
    use_temp_files()
    gs.activate_group(CHAT, "گروه تست")
    ge.set_expiry(CHAT, ge.FIVE_DAYS, title="گروه تست",
                  now=_utcnow() - timedelta(days=6))
    _mark_notified(str(abs(CHAT) - 1_000_000_000_000))
    # گروه هنوز در storage «منقضی و غیرفعال» نشده — ناظر اعلام داده ولی
    # همگام‌سازی نباید رأساً چیزی را غیرفعال کند.
    summary = sync_expiry_list()
    check("همگام‌سازی رکوردِ با گروه فعال را حذف نکرد",
          summary["removed_expired"] == 0, f"-> {summary}")
    check("گروه هنوز منقضی شمرده می‌شود", ge.is_expired(CHAT))
    check("مسدودسازی برقرار است", geh.blocks_message(CHAT, User(STRANGER_ID)))
    check("is_active را هیچ‌کس جز مسیرهای اصلی تغییر نداد",
          gs.is_active(CHAT) is True)


# ===========================================================================
# مسیر یابی (لاین ادمین)
# ===========================================================================
def test_dispatch_classification():
    print("\n### 🚦 دستور از لاین ادمین می‌رود")
    _p, kind = classify_priority("مهلت گروه")
    check("«مهلت گروه» لاین ادمین دارد", kind == LANE_ADMIN, f"-> {kind}")
    _p2, kind2 = classify_priority("مهلت\u200cگروه")
    check("با نیم‌فاصله هم لاین ادمین دارد", kind2 == LANE_ADMIN)
    _p3, kind3 = classify_priority("مهلت گروه من")
    check("متن‌های مشابه دستور، عادی می‌مانند", kind3 != LANE_ADMIN)
    _p4, kind4 = classify_priority("لیست انقضا")
    check("لیست انقضا همچنان ادمین است", kind4 == LANE_ADMIN)


def main():
    test_command_matching()
    test_format_remaining()
    test_remaining_message_format()
    test_handler_shows_real_remaining()
    test_handler_expired_group()
    test_handler_no_record()
    test_handler_permissions()
    test_handler_updates_title_after_rename()
    test_group_identity_is_by_id()
    test_handler_ignores_other_text()
    test_expiry_blocking_untouched()
    test_update_title_is_safe()
    test_sync_removes_finished_expired_only()
    test_sync_refreshes_titles()
    test_list_shows_live_status_after_renewal()
    test_sync_does_not_touch_expiry_enforcement()
    test_dispatch_classification()

    print("\n" + "=" * 52)
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
