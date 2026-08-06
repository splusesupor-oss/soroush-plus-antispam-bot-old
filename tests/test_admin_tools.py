"""تست ابزارهای مدیریتی جدید (لاگ، پاکسازی خودکار، decrement)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import modules.admin_tools as at
from modules.user_tracker import UserTracker

PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class U:
    def __init__(self, username=None, first=None, last=None):
        self.username = username
        self.first_name = first
        self.last_name = last


def test_display_name():
    check("@username", at.display_name(U("osine1")) == "@osine1")
    check("نام نمایشی", at.display_name(U(None, "علی", "رضا")) == "علی رضا")
    check("کاربر ناشناس", at.display_name(None) == "کاربر ناشناس")
    check("dict کاربر", at.display_name({"username": "fox", "first_name": "ف"}) == "@fox")


def test_admin_log():
    at._ADMIN_LOG_FILE.write_text("{}", encoding="utf-8")
    at.log_action(-1001, U("admin1"), "حذف پیام", target=U("user1"))
    at.log_action(-1001, U("admin2"), "اخطار", target=U("user2"))
    at.log_action(-2002, U("admin3"), "قفل کردن گروه")
    # جدا بودن گروه‌ها
    log1 = at.get_log(-1001)
    log2 = at.get_log(-2002)
    check("گروه ۱ دو اقدام دارد", len(log1) == 2, f"{len(log1)}")
    check("گروه ۲ یک اقدام دارد", len(log2) == 1, f"{len(log2)}")
    # هیچ ID عددی در خروجی نباشد
    text = at.format_log(-1001)
    check("لاگ فرمت شده ساخته شد", "لاگ مدیریتی" in text)
    check("شناسهٔ عددی در لاگ نیست", "-1001" not in text and "1001" not in text)
    check("نام ادمین در لاگ هست", "@admin1" in text or "admin1" in text)
    at.clear_log(-1001)
    at.clear_log(-2002)


def test_auto_cleanup_settings():
    at._CLEANUP_FILE.write_text("{}", encoding="utf-8")
    check("ساعت معتبر", at.valid_time("15:12") == "15:12")
    check("ساعت نامعتبر", at.valid_time("25:99") is None)
    check("ساعت بدقالب", at.valid_time("abc") is None)
    check("تعداد معتبر", at.valid_count("800") == 800)
    check("تعداد ۳۰۰۰ معتبر", at.valid_count("3000") == 3000)
    check("تعداد ۳۰۰۱ نامعتبر", at.valid_count("3001") is None)
    check("تعداد صفر نامعتبر", at.valid_count("0") is None)

    at.set_cleanup(-1003, "today", "15:12", 800)
    rec = at.get_cleanup(-1003)
    check("تنظیم ذخیره شد",
          rec and rec["time"] == "15:12" and rec["count"] == 800
          and rec["day"] == "today", f"{rec}")
    check("set_at ذخیره شد", rec and bool(rec.get("set_at")))
    check("scheduled_at ذخیره شد", rec and bool(rec.get("scheduled_at")))
    check("در همهٔ تنظیم‌ها هست", str(-1003) in at.all_cleanups())
    at.clear_cleanup(-1003)
    check("حذف تنظیم", at.get_cleanup(-1003) is None)


def test_scheduling_computation():
    from datetime import datetime, timedelta
    now = datetime(2026, 8, 6, 13, 30)
    # امروز + ساعتِ بعدی → همان روز
    s = at.compute_scheduled_at("today", "15:12", now)
    check("امروز ۱۵:۱۲ همان روز است",
          s.date() == now.date() and s.hour == 15 and s.minute == 12)
    # امروز + ساعتِ گذشته → فردا
    s2 = at.compute_scheduled_at("today", "01:30", now)
    check("امروزِ گذشته → فردا",
          (s2.date() - now.date()).days == 1 and s2.hour == 1 and s2.minute == 30)
    # فردا + ساعت → فردا
    s3 = at.compute_scheduled_at("tomorrow", "01:30", now)
    check("فردا ۰۱:۳۰ → فردا",
          (s3.date() - now.date()).days == 1 and s3.hour == 1)
    check("زمانِ معتبر نیست → None",
          at.compute_scheduled_at("today", "99:99", now) is None)


def test_user_tracker_decrement(tmpfile):
    tracker = UserTracker(spam_counts_file=str(tmpfile), threshold=5)
    tracker.reset_count(-1, 111)
    check("ابتداً صفر", tracker.get_count(-1, 111) == 0)
    tracker.increment(-1, 111)
    tracker.increment(-1, 111)
    check("دو اخطار", tracker.get_count(-1, 111) == 2)
    n = tracker.decrement(-1, 111)
    check("یک اخطار کم شد", n == 1 and tracker.get_count(-1, 111) == 1)
    n = tracker.decrement(-1, 111)
    check("به صفر رسید", n == 0)
    # decrement دوباره نباید منفی شود
    n = tracker.decrement(-1, 111)
    check("کمتر از صفر نمی‌رود", n == 0)
    # سایر کاربران دست‌نخورده‌اند
    tracker.increment(-1, 222)
    check("کاربر دیگر دست‌نخورده", tracker.get_count(-1, 222) == 1)


def test_group_lock_reuse():
    l1 = at.get_group_lock(-5001)
    l2 = at.get_group_lock(-5001)
    check("قفل مشترک همان شیء است", l1 is l2)


def main():
    test_display_name()
    test_admin_log()
    test_auto_cleanup_settings()
    test_scheduling_computation()
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        test_user_tracker_decrement(tmp)
    finally:
        os.unlink(tmp)
    test_group_lock_reuse()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
