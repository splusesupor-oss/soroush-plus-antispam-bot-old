# -*- coding: utf-8 -*-
"""جریان مجازات «نام تبلیغاتی» (modules/ad_name_enforcement).

پوشش: حذف پیام‌های کاربرِ قبل از مجازات (ردیاب/جاروی تاریخچه)، قفل
تک‌رخدادی و ادامهٔ پاکسازی پیام‌های بعدی، متن سکوت/اخراج طبق «تغییر
مجازات»، رهاسازی قفل هنگام شکست صف/RPC، مسیر ورود (join) با جاروی
محدود تاریخچه، و مسیر تغییر نام با known_chats_for_user.

بدون کلاینت واقعی اجرا می‌شود (همهٔ RPCها جعلی‌اند).
اجرا مستقیم: ``python3 tests/test_ad_name_enforcement.py``
"""
import asyncio
import inspect
import os
import sys
import tempfile
import traceback
from types import SimpleNamespace

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.environ.setdefault(
    "SOROUSH_BOT_DATA_DIR", tempfile.mkdtemp(prefix="ad-name-enforce-test-"))

from modules import ad_name_enforcement as enf  # noqa: E402
from modules import message_tracker  # noqa: E402
from modules import spam_history  # noqa: E402
from modules.group_id import normalize_group_id  # noqa: E402

CHAT = 5758486084
USER = 424242


# ---------------------------------------------------------------------------
# ابزار تست جعلی — دقیقاً همان امضاهایی که enforce استفاده می‌کند
# ---------------------------------------------------------------------------

class _Logger:
    def __init__(self):
        self.infos, self.errors, self.actions = [], [], []

    def log_info(self, msg):
        self.infos.append(str(msg))

    def log_error(self, msg):
        self.errors.append(str(msg))

    def log_action(self, *args):
        self.actions.append(args)


class _DeleteQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, chat_id, ids, priority=1):
        self.calls.append((chat_id, list(ids), priority))
        return len(ids)


class _Job(SimpleNamespace):
    pass


class _ModerationQueue:
    def __init__(self, accept=True):
        self.accept = accept
        self.jobs = []

    def enqueue(self, chat_id, action, *, operation, user_id=None,
                timeout_seconds=None, on_success=None, on_failure=None):
        if not self.accept:
            return False
        self.jobs.append(_Job(
            chat_id=chat_id, action=action, operation=operation,
            user_id=user_id, timeout_seconds=timeout_seconds,
            on_success=on_success, on_failure=on_failure))
        return True


class _AdminActions:
    def __init__(self):
        self.calls = []

    async def ban_user(self, chat_id, user_id,
                       reason="حذف دائمی به دلیل اسپم", *, user=None, chat=None):
        self.calls.append({
            "chat_id": chat_id, "user_id": user_id,
            "reason": reason, "user": user,
        })
        return True


class _Client:
    def __init__(self, history=()):
        self.history = list(history)
        self.sent_texts = []
        self.deleted = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_texts.append((chat_id, text))
        return SimpleNamespace(id=10_000 + len(self.sent_texts))

    async def delete_messages(self, chat_id, ids):
        self.deleted.append((chat_id, list(ids)))
        return []

    def iter_messages(self, chat_id, limit=None, wait_time=None):
        history = self.history if limit is None else self.history[:limit]

        async def _gen():
            for msg in history:
                yield msg
        return _gen()


class _Bot:
    def __init__(self, *, client=None, delete_queue=None, queue_accept=True):
        self.punished_users = set()
        self.logger = _Logger()
        self.message_delete_queue = delete_queue if delete_queue is not None else _DeleteQueue()
        self.moderation_queue = _ModerationQueue(accept=queue_accept)
        self.admin_actions = _AdminActions()
        self.outgoing_sender = None
        self.client = client or _Client()


def _user(name, user_id=USER):
    return SimpleNamespace(id=user_id, first_name=name,
                           last_name=None, username=None)


def _reset():
    message_tracker.reset_all()
    spam_history.clear_user(CHAT, USER)


async def _run_job(bot, index=0):
    job = bot.moderation_queue.jobs[index]
    result = await job.operation()
    if result and job.on_success is not None:
        await job.on_success(result)
    return result


def _info_index(bot, needle):
    for idx, line in enumerate(bot.logger.infos):
        if needle in line:
            return idx
    return -1


# ---------------------------------------------------------------------------
# سناریوها
# ---------------------------------------------------------------------------

async def _case_punish_deletes_messages_first():
    """کاربرِ پیام‌داده با نام تبلیغاتی: همهٔ پیام‌های ردیاب + پیام فعلی
    باید «قبل» از صدور مجازات در صف حذف قرار بگیرند."""
    _reset()
    bot = _Bot()
    message_tracker.add_message(CHAT, USER, 10, "سلام")
    message_tracker.add_message(CHAT, USER, 11, "چه خبر")
    ok = enf.enforce(bot, CHAT, USER, _user("دختر 💋"),
                     message_id=12, source="message")
    assert ok is True
    # پاکسازی بلافاصله و قبل از اجرای بن صف‌بندی شده است
    assert len(bot.message_delete_queue.calls) == 1
    _, ids, _ = bot.message_delete_queue.calls[0]
    assert ids == [10, 11, 12], ids
    # ترتیب لاگ: PURGE قبل از BAN QUEUED
    assert -1 < _info_index(bot, "AD NAME PURGE QUEUED") < _info_index(
        bot, "AD NAME BAN QUEUED")
    assert len(bot.moderation_queue.jobs) == 1
    assert await _run_job(bot) is True
    ban = bot.admin_actions.calls[0]
    assert ban["chat_id"] == CHAT and ban["user_id"] == USER
    assert ban["reason"] == "نام تبلیغاتی"
    # اعلان بعد از موفقیت بن ارسال می‌شود (ته‌خط: اخراج)
    assert len(bot.client.sent_texts) == 1
    _, text = bot.client.sent_texts[0]
    assert "نام تبلیغاتی" in text and "اخراج" in text
    assert _info_index(bot, "AD NAME BAN FINISHED") >= 0


async def _case_mute_mode_notice():
    """با «تغییر مجازات» روی سکوت، متن اعلان سکوت دائمی است و عملیات همان
    ban_user است (تبدیل به سکوت داخل AdminActions انجام می‌شود)."""
    _reset()
    bot = _Bot()
    message_tracker.add_message(CHAT, USER, 20, "پیام")
    original = enf.punishment_mode.is_mute
    enf.punishment_mode.is_mute = lambda chat_id: True
    try:
        assert enf.enforce(bot, CHAT, USER, _user("پسر گرم 🍑"),
                           message_id=20, source="message") is True
    finally:
        enf.punishment_mode.is_mute = original
    assert await _run_job(bot) is True
    assert bot.moderation_queue.jobs[0].action == "ban"
    _, text = bot.client.sent_texts[0]
    assert "سکوت دائم" in text


async def _case_duplicate_incident_still_purges():
    """پیام‌های بعدیِ همان کاربر تا لحظهٔ اعمال مجازات نباید بمانند: در
    رخداد تکراری دوباره بن صادر نمی‌شود ولی پیامِ تازه پاک می‌شود."""
    _reset()
    bot = _Bot()
    message_tracker.add_message(CHAT, USER, 30, "اول")
    assert enf.enforce(bot, CHAT, USER, _user("خانوم داغ"),
                       message_id=30, source="message") is True
    assert len(bot.moderation_queue.jobs) == 1
    assert len(bot.message_delete_queue.calls) == 1
    # رویداد دوم (مثلاً پیام بعدی قبل از اجرای RPC بن)
    message_tracker.add_message(CHAT, USER, 31, "دوم")
    assert enf.enforce(bot, CHAT, USER, _user("خانوم داغ"),
                       message_id=31, source="message") is True
    assert len(bot.moderation_queue.jobs) == 1  # بن دوباره صف نمی‌شود
    assert len(bot.message_delete_queue.calls) == 2
    _, ids, _ = bot.message_delete_queue.calls[1]
    assert 31 in ids, ids
    assert _info_index(bot, "AD NAME INCIDENT DUPLICATE SKIPPED") >= 0


async def _case_legit_user_untouched():
    _reset()
    bot = _Bot()
    message_tracker.add_message(CHAT, USER, 40, "سلام بچه‌ها")
    ok = enf.enforce(bot, CHAT, USER, _user("سارا احمدی"),
                     message_id=41, source="message")
    assert ok is False
    assert not bot.moderation_queue.jobs
    assert not bot.message_delete_queue.calls
    assert not bot.punished_users


async def _case_join_sweeps_history_when_tracker_empty():
    """ورود با نام تبلیغاتی و بدون پیامِ ردیاب‌شده: جاروی پس‌زمینهٔ محدود
    پیام‌های قبلیِ او را از صفحهٔ اخیر تاریخچه پیدا و پاک می‌کند."""
    _reset()
    mine = [SimpleNamespace(id=100 + i, sender_id=USER) for i in range(3)]
    others = [SimpleNamespace(id=200, sender_id=999)]
    history = [mine[0], others[0], mine[1], mine[2]]
    bot = _Bot(client=_Client(history))
    ok = enf.enforce(bot, CHAT, USER, _user("سکـس 💦"),
                     source="join")
    assert ok is True
    assert len(bot.moderation_queue.jobs) == 1  # بن بلافاصله صف شد
    assert await _run_job(bot) is True
    # جارو در پس‌زمینه کامل می‌شود و پیام‌های یافت‌شده حذف می‌شوند
    for _ in range(50):
        if bot.message_delete_queue.calls:
            break
        await asyncio.sleep(0.02)
    assert len(bot.message_delete_queue.calls) == 1
    _, ids, _ = bot.message_delete_queue.calls[0]
    assert ids == [100, 101, 102], ids
    assert _info_index(bot, "AD NAME HISTORY SWEEP COMPLETE") >= 0


async def _case_join_sweep_is_bounded():
    """سقف جارو (۳۰۰ پیام اخیر) رعایت می‌شود؛ ادعای حذفِ فراتر از آن نیست."""
    _reset()
    history = [SimpleNamespace(id=1000 + i, sender_id=USER) for i in range(320)]
    bot = _Bot(client=_Client(history))
    assert enf.enforce(bot, CHAT, USER, _user("کانال 🔞"), source="join")
    for _ in range(80):
        if bot.message_delete_queue.calls:
            break
        await asyncio.sleep(0.02)
    assert len(bot.message_delete_queue.calls) == 1
    _, ids, _ = bot.message_delete_queue.calls[0]
    assert len(ids) <= 300, len(ids)


async def _case_name_change_after_join():
    """تغییر نام به نام تبلیغاتی: گروه‌های شناخته‌شده از ردیاب هدف گرفته
    می‌شوند و همان جریان پاکسازی + مجازات اجرا می‌شود."""
    _reset()
    bot = _Bot()
    message_tracker.add_message(CHAT, USER, 50, "قبل از تغییر نام")
    chats = message_tracker.known_chats_for_user(USER)
    assert CHAT in chats, chats
    probe = SimpleNamespace(id=USER, first_name="دختر سکـ ـسی",
                            last_name=None, username=None)
    ad_reason = __import__("modules.ad_name_detector", fromlist=["reason"]).reason(probe)
    assert ad_reason is not None
    for chat_id in chats:
        assert enf.enforce(bot, chat_id, USER, probe,
                           source="name_change", ad_reason=ad_reason) is True
    _, ids, _ = bot.message_delete_queue.calls[0]
    assert 50 in ids, ids
    assert len(bot.moderation_queue.jobs) == 1
    assert await _run_job(bot) is True
    assert any("source=name_change" in line for line in bot.logger.infos)


async def _case_name_change_legit_rename_no_action():
    _reset()
    message_tracker.add_message(CHAT, USER, 60, "پیام")
    bot = _Bot()
    probe = SimpleNamespace(id=USER, first_name="سارا احمدی",
                            last_name=None, username=None)
    from modules import ad_name_detector
    assert ad_name_detector.reason(probe) is None
    assert enf.enforce(bot, CHAT, USER, probe, source="name_change") is False
    assert not bot.moderation_queue.jobs
    assert not bot.message_delete_queue.calls


async def _case_queue_rejection_releases_claim():
    """ردِ صف (رخداد در حال اجرا) قفل punished_users را رها می‌کند."""
    _reset()
    bot = _Bot(queue_accept=False)
    message_tracker.add_message(CHAT, USER, 70, "پیام")
    assert enf.enforce(bot, CHAT, USER, _user("زوری"), message_id=70) is True
    assert not bot.punished_users
    assert _info_index(bot, "AD NAME INCIDENT QUEUE DUPLICATE") >= 0


async def _case_ban_failure_releases_claim():
    """شکست RPC بن قفل را رها می‌کند تا رویداد بعدی دوباره تلاش کند."""
    _reset()
    bot = _Bot()
    message_tracker.add_message(CHAT, USER, 80, "پیام")
    assert enf.enforce(bot, CHAT, USER, _user("بیو‌گرافی چک"),
                       message_id=80) is True
    key = next(iter(bot.punished_users))
    job = bot.moderation_queue.jobs[0]
    await job.on_failure(RuntimeError("rpc down"))
    assert key not in bot.punished_users
    assert _info_index(bot, "AD NAME BAN FAILED") == -1
    assert any("AD NAME BAN FAILED" in line for line in bot.logger.errors)


def test_punish_key_matches_handler_formula():
    """کلید رخداد باید با _punishment_key مسیر پیام هماهنگ بماند."""
    expected = f"{normalize_group_id(CHAT)}:{USER}"
    assert enf._punish_key(CHAT, USER) == expected
    assert enf._punish_key(f"-100{CHAT}", str(USER)) == expected


# سناریوهای async در قالب تست‌های sync تا بدون افزونه اجرا شوند
def test_punish_deletes_messages_first():
    asyncio.run(_case_punish_deletes_messages_first())


def test_mute_mode_notice():
    asyncio.run(_case_mute_mode_notice())


def test_duplicate_incident_still_purges():
    asyncio.run(_case_duplicate_incident_still_purges())


def test_legit_user_untouched():
    asyncio.run(_case_legit_user_untouched())


def test_join_sweeps_history_when_tracker_empty():
    asyncio.run(_case_join_sweeps_history_when_tracker_empty())


def test_join_sweep_is_bounded():
    asyncio.run(_case_join_sweep_is_bounded())


def test_name_change_after_join():
    asyncio.run(_case_name_change_after_join())


def test_name_change_legit_rename_no_action():
    asyncio.run(_case_name_change_legit_rename_no_action())


def test_queue_rejection_releases_claim():
    asyncio.run(_case_queue_rejection_releases_claim())


def test_ban_failure_releases_claim():
    asyncio.run(_case_ban_failure_releases_claim())


def _run_all():
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)
             and not inspect.iscoroutinefunction(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            traceback.print_exc()
            print(f"FAIL {name}")
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
