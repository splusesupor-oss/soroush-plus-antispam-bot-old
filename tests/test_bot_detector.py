"""تستِ قابلیتِ تشخیصِ رباتِ دیگر و غیرفعال‌سازیِ خودکارِ روباه.

از مسیرِ واقعیِ ``handlers.message_handler.handle_new_message`` (با هارنسِ
هم‌نامِ test_admin_commands) اجرا می‌شود تا مطمئن شویم همان مسیرِ واقعیِ ربات
رفتارِ درست دارد.
"""
import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import modules.bot_detector as bd

PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


def _load_harness():
    spec = importlib.util.spec_from_file_location(
        "tac", str(ROOT / "tests" / "test_admin_commands.py"))
    tac = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tac)
    return tac


def test_bot_detection_flow():
    import handlers.message_handler as mh
    tac = _load_harness()

    # User را برای شبیه‌سازیِ فیلدِ bot آماده کن
    def __init__(self, uid, name="علی", username=None, bot=False):
        self.id = uid
        self.first_name = name
        self.last_name = None
        self.username = username
        self.bot = bot
    tac.User.__init__ = __init__

    owner = tac._owner_id()
    CHAT = tac.CHAT

    async def handle(bot, event, sender_override):
        real = event.get_sender
        async def gs():
            return sender_override
        event.get_sender = gs
        try:
            await mh.handle_new_message(bot, event)
        finally:
            event.get_sender = real

    # --- ۱) رباتِ دیگر → غیرفعال + اطلاع‌رسانی ---
    bd._FILE.unlink(missing_ok=True)
    other_bot = tac.User(777000, name="ربات گروه", username="otherbot", bot=True)
    bot = tac.build_bot()
    ev = tac.Event("سلام", owner)
    asyncio.run(handle(bot, ev, other_bot))
    check("ربات دیگر غیرفعال شد", bd.is_disabled(CHAT))
    check("نام ربات ذخیره شد (@otherbot)",
          bd.disabled_bot_name(CHAT) == "@otherbot")
    check("پیام اطلاع‌رسانی ارسال شد",
          any("به دلیل فعال بودن ربات" in r for r in ev.replies)
          and any("otherbot" in r for r in ev.replies), f"{ev.replies}")

    # --- ۲) در گروهِ غیرفعال، پیام بعدی (حتی از ربات) دور ریخته می‌شود ---
    bot2 = tac.build_bot()
    ev2 = tac.Event("پیام دیگر", owner)
    asyncio.run(handle(bot2, ev2, other_bot))
    check("پس از غیرفعال، هیچ پاسخی داده نمی‌شود", len(ev2.replies) == 0,
          f"{ev2.replies}")

    # --- ۳) کاربرِ عادی هرگز ربات تشخیص داده نمی‌شود ---
    bd._FILE.unlink(missing_ok=True)
    normal = tac.User(111, name="علی", username="ali", bot=False)
    bot3 = tac.build_bot()
    ev3 = tac.Event("سلام", owner)
    asyncio.run(handle(bot3, ev3, normal))
    check("کاربر عادی ربات نیست", not bd.is_disabled(CHAT))

    # --- ۴) حسابِ خودِ روباه هدف نمی‌شود ---
    bd._FILE.unlink(missing_ok=True)
    fox_self = tac.User(getattr(bot, "bot_account_id", 555),
                        name="aifox", username="aifox", bot=True)
    bot4 = tac.build_bot()
    ev4 = tac.Event("پیام", owner)
    asyncio.run(handle(bot4, ev4, fox_self))
    check("حسابِ خودِ روباه هدف نمی‌شود", not bd.is_disabled(CHAT))

    # --- ۵) فعال‌سازیِ دوباره توسط مالک ---
    bd.disable_for_bot(CHAT, other_bot)
    bot5 = tac.build_bot()
    ev5 = tac.Event(bd.REENABLE_COMMAND, owner)
    asyncio.run(handle(bot5, ev5, tac.User(owner, name="مالک", username="osine1")))
    check("فعال‌سازیِ دوباره پاسخ داد",
          any("دوباره فعال شد" in r for r in ev5.replies), f"{ev5.replies}")
    check("بعد از فعال‌سازی دیگر غیرفعال نیست", not bd.is_disabled(CHAT))

    # پاک‌سازیِ وضعیت
    bd._FILE.unlink(missing_ok=True)


def main():
    test_bot_detection_flow()
    print(f"\n=== bot_detector: PASSED={PASSED} FAILED={FAILED} ===")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
