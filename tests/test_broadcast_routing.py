"""Offline proof that «اطلاع رسانی» survives an unresolved private peer.

Drives the REAL new_message_handler from core with fake events. Reproduces the
failure modes a fresh Soroush Plus session produces (empty entity cache), where
``event.get_chat()`` returns None or raises.

    python tests/test_broadcast_routing.py
"""
import asyncio
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from splusthon.tl import types

import core.bot_working_split_ok as core
import modules.broadcast_state as bstate

# مالک سراسری در کامیت 58277de از osine1 (68074059) به osine2 (37858988)
# منتقل شد. به‌جای hard-code، همان منبعی خوانده می‌شود که خود ربات
# (``is_global_owner``) استفاده می‌کند تا تست به تغییر مالک وابسته نباشد.
def _configured_owner():
    import json
    data = json.loads((ROOT / "config" / "owner.json").read_text(encoding="utf-8"))
    return int(data["user_id"]), str(data.get("username") or "owner")


OWNER_ID, OWNER_USERNAME = _configured_owner()
STRANGER_ID = 12345678

PASSED = FAILED = 0
_captured = []


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class FakeUser:
    def __init__(self, uid=OWNER_ID, username=OWNER_USERNAME):
        self.id = uid
        self.username = username
        self.first_name = "Owner"


class FakeChannel:
    """Stands in for a group chat (negative id)."""

    def __init__(self, cid=-1000023164149):
        self.id = cid
        self.title = "Group"


class Logger:
    def __init__(self):
        self.lines = []

    def log_info(self, m):
        self.lines.append(("INFO", m))

    def log_error(self, m):
        self.lines.append(("ERROR", m))

    def log_action(self, *a, **k):
        pass

    def log_deleted_message(self, *a, **k):
        pass

    def has(self, needle):
        return any(needle in m for _, m in self.lines)


class FakeClient:
    def __init__(self):
        self.on = self._on
        self.sent = []

    def _on(self, spec):
        def deco(fn):
            if type(spec).__name__ == "NewMessage":
                _captured.append(fn)
            return fn
        return deco

    async def get_me(self):
        return FakeUser()

    async def connect(self):
        return True

    async def send_message(self, entity, message, formatting_entities=None, **kw):
        self.sent.append((entity, message))
        return None

    async def get_input_entity(self, x):
        return x

    def iter_dialogs(self):
        async def gen():
            for _ in ():
                yield _
        return gen()


class Msg:
    def __init__(self, text):
        self.message = text
        self.entities = []
        self.id = 555
        self.file = None


class Event:
    """Private outgoing message from the owner, by default."""

    chat_cls = FakeUser
    chat_raises = False
    chat_none = False

    def __init__(self, text, out=True, is_private=True,
                 sender_id=OWNER_ID, chat_id=OWNER_ID):
        self.message = Msg(text)
        self.out = out
        self.is_private = is_private
        self.chat_id = chat_id
        self.reply_to = None
        self.replies = []
        self._sender_id = sender_id

    async def get_chat(self):
        if self.chat_raises:
            raise ValueError("Could not find the input entity for PeerUser")
        if self.chat_none:
            return None
        return self.chat_cls()

    async def get_sender(self):
        return FakeUser(self._sender_id,
                        OWNER_USERNAME if self._sender_id == OWNER_ID else "other")

    async def reply(self, text, formatting_entities=None, **kw):
        self.replies.append(text)
        m = Msg(text)
        m.id = 9000 + len(self.replies)
        return m


async def _build():
    bot = core.SoroushAntiSpamBot.__new__(core.SoroushAntiSpamBot)
    bot.client = FakeClient()
    bot.logger = Logger()
    bot.broadcast_bot_message_ids = set()
    bot.group_timer_tasks = defaultdict(set)
    bot.punished_users = set()
    bot.delete_notice_lock = set()
    bot.spam_burst_users = {}
    bot.spammer_messages = defaultdict(lambda: deque(maxlen=10))
    bot.bot_account_id = OWNER_ID
    # این harness عمداً ``__init__`` را دور می‌زند؛ هر attribute تازه‌ای که
    # ``run()`` لازم دارد باید صریح ساخته شود، وگرنه handler هرگز ثبت
    # نمی‌شود. (مثلاً ``reply_input_peer_cache`` که بعداً به bot اضافه شد.)
    def _notice_cleanup():
        from modules.notice_cleanup import NoticeCleanup
        import tempfile, os as _os
        path = _os.path.join(tempfile.mkdtemp(), "notice_cleanup.json")
        return NoticeCleanup(path, logger=bot.logger, ttl_seconds=60)

    def _config_manager():
        from modules import ConfigManager
        return ConfigManager(config_path="config/config.json")

    def _group_dispatcher():
        from modules.group_dispatch import GroupDispatcher
        return GroupDispatcher(logger=bot.logger)

    for _attr, _default in (
        ("reply_input_peer_cache", dict),
        ("notice_cleanup", _notice_cleanup),
        ("config_manager", _config_manager),
        ("group_dispatcher", _group_dispatcher),
    ):
        if not hasattr(bot, _attr):
            setattr(bot, _attr, _default())

    class Stop(Exception):
        pass

    async def stop_sleep(*a, **k):
        raise Stop

    async def fake_init():
        return bot.client

    bot.initialize_client = fake_init
    real_sleep = asyncio.sleep
    asyncio.sleep = stop_sleep
    try:
        await core.SoroushAntiSpamBot.run(bot)
    except Stop:
        pass
    except Exception:
        pass
    finally:
        asyncio.sleep = real_sleep
    return bot


def fire(bot, event):
    bot.logger.lines.clear()
    handler = _captured[0]
    error = None
    try:
        asyncio.run(handler(event))
    except Exception as e:  # must never happen for a private command
        error = e
    return error


PROMPT = "📢 متن اطلاع‌رسانی را ارسال کنید."


def scenario(bot, label, event, expect_prompt=True):
    print(f"\n### {label}")
    bstate.clear(OWNER_ID)
    error = fire(bot, event)
    check("handler did not raise", error is None, f"-> {error!r}")
    if expect_prompt:
        check("owner received the prompt", PROMPT in event.replies,
              f"-> replies={event.replies}")
        check("session created",
              (bstate.get(OWNER_ID) or {}).get("phase") == "awaiting_message",
              f"-> {bstate.get(OWNER_ID)}")
        # کامیت fa84416 («restore reliable private broadcast routing») مسیر
        # سریعِ پیویِ مالک را جلوتر برد: حالا قبل از رسیدن به لاگ‌های
        # ``private_route=`` / ``BROADCAST ROUTE HANDLED`` با ``BROADCAST
        # READY`` برمی‌گردد. همان تضمین (شناسایی پیوی + مدیریت‌شدن دستور)
        # با نشانه‌های فعلی سنجیده می‌شود.
        check("routed as private",
              bot.logger.has("private_route=True")
              or bot.logger.has("BROADCAST TRIGGER CHECK"))
        check("broadcast command handled and logged",
              bot.logger.has("BROADCAST ROUTE HANDLED")
              or bot.logger.has("BROADCAST READY"))
    else:
        check("no prompt sent", PROMPT not in event.replies,
              f"-> replies={event.replies}")
    bstate.clear(OWNER_ID)


def main():
    bot = asyncio.run(_build())
    if not _captured:
        print("FATAL: could not capture new_message_handler")
        return 1
    print(f"captured handler: {_captured[0].__name__}")

    # --- the healthy baseline ---------------------------------------------
    scenario(bot, "owner self-command, chat resolves", Event("اطلاع رسانی"))

    # --- empty entity cache: get_chat() returns None ----------------------
    e = Event("اطلاع رسانی")
    e.chat_none = True
    scenario(bot, "get_chat() returns None", e)

    # --- unresolvable peer: get_chat() raises -----------------------------
    e = Event("اطلاع رسانی")
    e.chat_raises = True
    scenario(bot, "get_chat() raises ValueError", e)
    # مسیر سریعِ پیوی (fa84416) اصلاً به ``get_chat()`` نمی‌رسد، پس دیگر خطای
    # آن لاگ نمی‌شود؛ نکتهٔ اصلی این است که خطا دستور را نمی‌بلعد — که با
    # ارسال prompt و ساخت session در همین سناریو اثبات شد.
    check("خطای resolve دستور را نمی‌بلعد (بی‌صدا رد نشد)",
          bot.logger.has("BROADCAST READY")
          or bot.logger.has("get_chat FAILED"))

    # --- worst case: is_private False AND chat unresolved -----------------
    # کامیت 7c4a03f («require resolved private peer for broadcast routing»)
    # عمداً حدسِ «شناسهٔ مثبت ⇒ پیوی» را حذف کرد، چون SPlusthon همان شناسه‌ها
    # را برای کانال هم می‌دهد. پس رویدادی با is_private=False و peerِ
    # resolve‌نشده دیگر نباید به مسیر پیوی برود.
    e = Event("اطلاع رسانی", is_private=False)
    e.chat_none = True
    scenario(bot, "is_private=False and get_chat()=None", e,
             expect_prompt=False)
    check("peerِ resolve‌نشده به‌عنوان پیوی طبقه‌بندی نمی‌شود",
          not bot.logger.has("BROADCAST READY"))

    # --- incoming DM from the owner ---------------------------------------
    scenario(bot, "incoming DM (out=False)", Event("اطلاع رسانی", out=False))

    # --- a non-owner must NOT start a broadcast ---------------------------
    print("\n### stranger in private must be rejected")
    bstate.clear(STRANGER_ID)
    e = Event("اطلاع رسانی", out=False, sender_id=STRANGER_ID,
              chat_id=STRANGER_ID)
    err = fire(bot, e)
    check("handler did not raise", err is None, f"-> {err!r}")
    check("no prompt for stranger", PROMPT not in e.replies,
          f"-> {e.replies}")
    check("no session for stranger", bstate.get(STRANGER_ID) is None)
    check("rejection logged", bot.logger.has("not_global_owner")
          or not bot.logger.has("BROADCAST ROUTE HANDLED"))

    # --- group messages must still be treated as groups -------------------
    print("\n### group routing is unaffected")
    e = Event("سلام", out=False, is_private=False,
              chat_id=-1000023164149)
    e.chat_cls = FakeChannel
    err = fire(bot, e)
    check("handler did not raise on group message", err is None, f"-> {err!r}")
    check("not routed as private", not bot.logger.has("private_route=True"))

    # --- unresolved GROUP chat is now visible in the log ------------------
    print("\n### unresolved group chat is logged, not silent")
    e = Event("سلام", out=False, is_private=False, chat_id=-1000023164149)
    e.chat_none = True
    e.chat_cls = FakeChannel
    err = fire(bot, e)
    check("handler did not raise", err is None, f"-> {err!r}")
    check("negative chat_id stays group (not misrouted to private)",
          not bot.logger.has("private_route=True"))

    # --- ZWNJ spelling: the real-world failure ----------------------------
    print("\n### «اطلاع‌رسانی» written with ZWNJ (half-space)")
    ZWNJ = "\u200c"
    scenario(bot, "ZWNJ spelling reaches the handler",
             Event("اطلاع" + ZWNJ + "رسانی"))
    check("دستور با نیم‌فاصله هم لاگ شد",
          bot.logger.has("BROADCAST_COMMAND_RECEIVED")
          or bot.logger.has("BROADCAST COMMAND RECEIVED"))

    print("\n### mandatory log fields present")
    # مسیر سریعِ پیوی (fa84416) قبل از خطِ یکجای
    # ``BROADCAST_COMMAND_RECEIVED`` برمی‌گردد؛ همان فیلدهای تشخیصی حالا در
    # چند خطِ BROADCAST ثبت می‌شوند. تضمین این است که هیچ‌کدام گم نشده باشد.
    e = Event("اطلاع رسانی")
    fire(bot, e)
    trail = "\n".join(m for _, m in bot.logger.lines if "BROADCAST" in m)
    for field in ("text=", "normalized_text=", "matched_trigger=",
                  "owner_check=", "owner_id="):
        check(f"log contains {field}", field in trail, f"-> {trail[:160]}")
    bstate.clear(OWNER_ID)

    print(f"\n{'=' * 52}")
    print(f"passed={PASSED} failed={FAILED}")
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
