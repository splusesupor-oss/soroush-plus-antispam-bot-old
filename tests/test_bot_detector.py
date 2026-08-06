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


def test_partial_entity_bot_none_resolved_via_get_entity():
    """علتِ اصلیِ اسکرین‌شات: senderِ خلاصه با bot=None باید با get_entity قطعی شود."""
    import handlers.message_handler as mh
    import types
    tac = _load_harness()

    def __init__(self, uid, name="علی", username=None, bot=False):
        self.id = uid
        self.first_name = name
        self.last_name = None
        self.username = username
        self.bot = bot
    tac.User.__init__ = __init__

    owner = tac._owner_id()
    CHAT = tac.CHAT

    # کاربرِ واقعیِ «ربات» که entityِ خلاصه‌اش bot=None است، ولی get_entity
    # (GetUsers) آن را با bot=True برمی‌گرداند — همان سناریوی واقعی.
    partial_bot = tac.User(999888, name="bot", username="bot", bot=None)

    class Client:
        async def get_entity(self, entity):
            # شبیه‌سازیِ GetUsers: user کامل با bot=True
            return tac.User(999888, name="bot", username="bot", bot=True)
        async def get_messages(self, *a, **k): return []
        async def delete_messages(self, *a, **k): return None
        async def send_message(self, *a, **k): return None

    class GA:
        async def lock_group(self, c): pass
        async def unlock_group(self, c): pass

    bot = types.SimpleNamespace(
        client=Client(), logger=_Logger(),
        config_manager=types.SimpleNamespace(get=lambda k, d=None: d),
        tracker=types.SimpleNamespace(get_count=lambda *a: 0, increment=lambda *a: 0,
                                      reset_count=lambda *a: None, decrement=lambda *a: 0),
        detector=types.SimpleNamespace(is_spam=lambda *a: (False, None),
                                       check_message=lambda *a: (False, None)),
        group_timer_tasks={}, bot_account_id=555, punished_users=set(),
        spam_burst_messages={}, spammer_messages={}, spam_burst_users=set(),
        moderation_queue=types.SimpleNamespace(enqueue=lambda *a: True),
        admin_actions=types.SimpleNamespace(), group_actions=GA(),
        cleanup_tasks={})

    bd._FILE.unlink(missing_ok=True)
    bd._KNOWN_BOT_IDS.clear()
    bd._KNOWN_HUMAN_IDS.clear()

    ev = tac.Event("سلام", owner)
    # فرستنده = همان entityِ خلاصه با bot=None
    async def gs(): return partial_bot
    ev.get_sender = gs
    asyncio.run(mh.handle_new_message(bot, ev))

    check("senderِ خلاصه با bot=None، با get_entity ربات تشخیص داده شد",
          bd.is_disabled(CHAT), f"{ev.replies}")
    check("پیام اطلاع‌رسانی با نام ربات",
          any("to دلیل فعال بودن ربات" in r and "bot" in r for r in ev.replies)
          or any("ربات" in r for r in ev.replies), f"{ev.replies}")

    bd._FILE.unlink(missing_ok=True)
    bd._KNOWN_BOT_IDS.clear()
    bd._KNOWN_HUMAN_IDS.clear()


class _Logger:
    def log_info(self, *a, **k): pass
    def log_error(self, *a, **k): pass


def main():
    test_bot_detection_flow()
    test_partial_entity_bot_none_resolved_via_get_entity()
    print(f"\n=== bot_detector: PASSED={PASSED} FAILED={FAILED} ===")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
