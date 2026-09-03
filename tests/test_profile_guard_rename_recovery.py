"""️ رگرسیون: بلوک نام ممنوعه → تغییر نام → بازیابی دسترسی.

سناریوی باگ گزارش‌شده:
    ۱. کاربری که نامش کلمهٔ ممنوعه دارد → بلاک + اعلان «دسترسی شما از
       ربات حذف شد».
    ۲. کاربر نامش را عوض می‌کند.
    ۳. پیام بعدی باید رکورد کهنه را پاک کند (unblock) و اعلان تکراری
       نفرستد و پیام به‌رویش عادی پردازش شود.
    ۴. اگر نام هنوز ممنوعه باشد، بلوک و اعلان همچنان اعمال شود.

قاعدهٔ کلیدی: فقط ``reason()`` (چک زنده) منبع تشخیص است؛ دلیل قدیمیِ
رکورد ذخیره‌شده هرگز به‌عنوان profile_reason تزریق نمی‌شود.

    python -m pytest tests/test_profile_guard_rename_recovery.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import access_profile_guard as guard
from modules import group_storage
from handlers.message_handler import handle_new_message

NOTICE = "دسترسی شما از ربات حذف شد"
NORMAL_REPLY_MARKER = "جانم"  # SIMPLE_REPLIES["ربات"]


class MockEvent:
    """رویداد آزمون — هم‌شکل با test_profile_access_guard.py"""

    def __init__(self, text, user_id=2001, first_name="رضا",
                 username=None, is_private=False):
        self.raw_text = text
        self.message = SimpleNamespace(message=text, id=1, entities=None)
        self.chat_id = 1001
        self.sender_id = user_id
        self.is_private = is_private
        self.sender = SimpleNamespace(
            id=user_id,
            first_name=first_name,
            last_name=None,
            username=username,
            bot=False,
        )
        self.replies = []

    async def reply(self, msg, *args, **kwargs):
        self.replies.append(msg)
        return SimpleNamespace(id=len(self.replies))

    async def get_sender(self):
        return self.sender

    async def get_chat(self):
        return SimpleNamespace(id=self.chat_id, title="گروه تست")


def _make_bot(user_id):
    me = SimpleNamespace(id=user_id, first_name="رضا", last_name=None,
                         username=None, bot=False)
    return SimpleNamespace(
        logger=MagicMock(),
        client=SimpleNamespace(
            get_entity=AsyncMock(return_value=me),
            send_message=AsyncMock(),
        ),
        tracker=MagicMock(get_count=lambda c, u: 0),
        punished_users=set(),
        is_spam_locked=lambda k: False,
        detector=SimpleNamespace(
            check_banned_words=lambda text, chat_id: (False, None)),
    )


async def _settle():
    """اجرای taskهای fire-and-forget پاسخ (مثل _schedule_reply)."""
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.fixture
def isolated_guard(tmp_path, monkeypatch):
    """گارد و گروه‌ها روی فایل موقت — هیچ فایل واقعی پروژه دست نمی‌خورد."""
    monkeypatch.setattr(guard, "FILE", tmp_path / "profile_access_blocks.json")
    monkeypatch.setattr(guard, "_CACHE", None)
    monkeypatch.setattr(group_storage, "FILE", tmp_path / "groups.json")
    monkeypatch.setattr(group_storage, "_cache", None)
    monkeypatch.setattr(group_storage, "_cache_mtime", None)
    group_storage.activate_group(1001, "گروه تست")
    return guard


# ===========================================================================
# سناریوی اصلی: نام ممنوع → بلوک → اعلان → تغییر نام → unblock → پردازش عادی
# ===========================================================================
def test_rename_recovery_no_stale_notice(isolated_guard):
    async def scenario():
        g = isolated_guard
        user_id = 5550001
        g.unblock(user_id)
        bot = _make_bot(user_id)

        # ۱) نام ممنوعه → بلوک + اعلان واحد، بدون پاسخ عادی ربات
        bad = MockEvent("ربات", user_id=user_id, first_name="👑پهلوی👑")
        await handle_new_message(bot, bad)
        assert g.is_blocked(user_id) is True
        assert len(bad.replies) == 1
        assert NOTICE in bad.replies[0]

        # ۲) نام به حالت سالم برمی‌گردد → پیام بعدی: unblock + بدون اعلان
        #    + پردازش عادی (پاسخ «جانم ؟ 🦊» برای دستور «ربات»)
        clean = MockEvent("ربات", user_id=user_id, first_name="رضا علوی")
        await handle_new_message(bot, clean)
        await _settle()
        assert g.is_blocked(user_id) is False
        assert g.record_for(user_id) is None
        assert all(NOTICE not in r for r in clean.replies)
        assert any(NORMAL_REPLY_MARKER in r for r in clean.replies)

        # ۳) دوباره نام ممنوعه → بلوک و اعلان برگردند (چک زنده فعال است)
        bad_again = MockEvent("ربات", user_id=user_id,
                              first_name="فرزند ایران")
        await handle_new_message(bot, bad_again)
        assert g.is_blocked(user_id) is True
        assert any(NOTICE in r for r in bad_again.replies)
        assert g.record_for(user_id)["reason"] == "فرزند ایران"

        g.unblock(user_id)

    asyncio.run(scenario())


# ===========================================================================
# اگر نام هنوز ممنوعه باشد، بلوک و اعلان تکرار شود
# ===========================================================================
def test_still_forbidden_stays_blocked_and_notified(isolated_guard):
    async def scenario():
        g = isolated_guard
        user_id = 5550002
        g.unblock(user_id)
        bot = _make_bot(user_id)

        first = MockEvent("ربات", user_id=user_id, first_name="شاهزاده")
        await handle_new_message(bot, first)
        assert g.is_blocked(user_id) is True
        assert len(first.replies) == 1
        assert NOTICE in first.replies[0]

        second = MockEvent("ربات", user_id=user_id,
                           first_name="شاهزاده پهلوی")
        await handle_new_message(bot, second)
        assert g.is_blocked(user_id) is True
        assert any(NOTICE in r for r in second.replies)
        # دلیل ذخیره‌شده همواره از چک زنده می‌آید، نه از رکورد قبلی
        live_reason = g.reason(second.sender)
        assert live_reason is not None
        assert g.record_for(user_id)["reason"] == live_reason

        g.unblock(user_id)

    asyncio.run(scenario())


# ===========================================================================
# رکورد کهنهٔ ازپیش‌موجود (نسخهٔ قدیمی باگ) با اولین پیام تمیز پاک شود
# ===========================================================================
def test_preexisting_stale_record_cleared_on_first_clean_message(
        isolated_guard):
    async def scenario():
        g = isolated_guard
        user_id = 5550003
        # شبیه‌سازی رکوردی که نسخهٔ قدیمیِ باگ‌دار ربات جا گذاشته
        g.block(user_id, "شاه")
        assert g.is_blocked(user_id) is True

        bot = _make_bot(user_id)
        clean = MockEvent("ربات", user_id=user_id, first_name="علی رضایی")
        await handle_new_message(bot, clean)
        await _settle()

        assert g.is_blocked(user_id) is False
        assert g.record_for(user_id) is None
        assert all(NOTICE not in r for r in clean.replies)
        assert any(NORMAL_REPLY_MARKER in r for r in clean.replies)

    asyncio.run(scenario())


# ===========================================================================
# تست واحد: ماشین حالت sync_block_state — تزریق دلیل قدیمی ممنوع
# ===========================================================================
def test_sync_block_state_never_injects_stale_reason(isolated_guard):
    g = isolated_guard
    user_id = 5550004
    g.unblock(user_id)
    bad = SimpleNamespace(id=user_id, first_name="فرزند ایران",
                          last_name=None, username=None)
    clean = SimpleNamespace(id=user_id, first_name="رضا",
                            last_name=None, username=None)

    # نام فعلاً ممنوع → blocked با دلیل زنده
    status, reason = g.sync_block_state(bad, user_id)
    assert (status, reason) == (g.STATUS_BLOCKED, "فرزند ایران")
    assert g.is_blocked(user_id) is True

    # رکورد قدیمی وجود دارد ولی چک زنده تمیز است → restored و دلیل None
    status, reason = g.sync_block_state(clean, user_id)
    assert (status, reason) == (g.STATUS_RESTORED, None)
    assert g.is_blocked(user_id) is False
    assert g.record_for(user_id) is None

    # بدون هیچ اطلاعات پروفایل → حالت unknown؛ اگر بلوک نبود، clean
    status, reason = g.sync_block_state(None, user_id, None)
    assert (status, reason) == (g.STATUS_CLEAN, None)

    # بدون اطلاعات پروفایل ولی بلوک فعال → held ساکت؛ دلیل قدیمی نه تزریق
    # می‌شود و نه تغییر می‌کند
    g.block(user_id, "آمریکا")
    status, reason = g.sync_block_state(None, user_id, None)
    assert (status, reason) == (g.STATUS_HELD, None)
    assert g.is_blocked(user_id) is True
    assert g.record_for(user_id)["reason"] == "آمریکا"

    # user_id خالی هیچ‌وقت خطا نمی‌دهد
    status, reason = g.sync_block_state(bad, None)
    assert (status, reason) == (g.STATUS_CLEAN, None)

    g.unblock(user_id)


def test_notice_text_is_the_shared_constant(isolated_guard):
    assert isolated_guard.RESTRICTION_NOTICE.startswith(
        "⚠️ دسترسی شما از ربات حذف شد.")
    assert isolated_guard.RESTRICTION_NOTICE_BOLD_LENGTH == len(
        "⚠️ دسترسی شما از ربات حذف شد.")


# ===========================================================================
# رگرسیون باگ گزارش‌شده (کلمهٔ دقیقِ کاربر: «شاه»):
# نام ممنوع → بلوک + اعلان → اصلاح نام → اعلان تکراری ممنوع
# ===========================================================================
def test_shah_rename_lifecycle_no_repeat_notice(isolated_guard):
    async def scenario():
        g = isolated_guard
        user_id = 5550010
        g.unblock(user_id)
        bot = _make_bot(user_id)

        # ۱) نام «شاه» → بلوک + اعلان
        bad = MockEvent("ربات", user_id=user_id, first_name="شاه")
        await handle_new_message(bot, bad)
        assert g.is_blocked(user_id) is True
        assert g.record_for(user_id)["reason"] == "شاه"
        assert len(bad.replies) == 1
        assert NOTICE in bad.replies[0]

        # ۲) کاربر نامش را اصلاح می‌کند → پیام بعدی: بدون اعلان تکراری،
        #    رکورد کهنه حذف، پردازش عادی
        clean = MockEvent("ربات", user_id=user_id, first_name="رضا")
        await handle_new_message(bot, clean)
        await _settle()
        assert g.is_blocked(user_id) is False
        assert g.record_for(user_id) is None
        assert all(NOTICE not in r for r in clean.replies)
        assert any(NORMAL_REPLY_MARKER in r for r in clean.replies)

        # ۳) «شاهین» قربانی «شاه» نمی‌شود (بدون false positive)
        shahin = MockEvent("ربات", user_id=user_id, first_name="شاهین")
        await handle_new_message(bot, shahin)
        await _settle()
        assert g.is_blocked(user_id) is False
        assert all(NOTICE not in r for r in shahin.replies)

        g.unblock(user_id)

    asyncio.run(scenario())


# ===========================================================================
# رگرسیون ساختاری: مسیر پیام‌های معمولیِ core (process_incoming_message)
# باید همان منبع واحد تصمیم‌گیری (sync_block_state) را استفاده کند و
# هیچ‌گاه دلیلِ رکورد ذخیره‌شده را به‌عنوان دلیل فعلی تزریق نکند —
# که دقیقاً ریشهٔ همین باگ بود: همان مسیر، رکورد کهنه را مجدداً اعمال
# می‌کرد و کاربری که نامش را اصلاح کرده بود، برای همیشه با همان اعلان
# تکراری بلوک می‌ماند (درحالی‌که مسیرهای اولویت‌دار و هندلر درست بودند).
# ===========================================================================
def test_core_ordinary_message_lane_uses_single_decision_source():
    source = (ROOT / "core" / "bot_working_split_ok.py").read_text(
        encoding="utf-8")
    start = source.index("async def process_incoming_message(event):")
    end = source.index("@self.client.on(events.NewMessage())", start)
    lane = source[start:end]

    # مسیر باید از sync_block_state استفاده کند (منبع واحد تصمیم‌گیری)
    assert "access_profile_guard.sync_block_state(" in lane
    # الگوی باگ: تزریق دلیل قدیمی از رکورد ذخیره‌شده — نباید باقی مانده باشد
    assert "record_for(" not in lane, (
        "مسیر process_incoming_message دوباره رکورد ذخیره‌شده را به‌عنوان "
        "دلیل تشخیص می‌خواند — باگ بلوک ابدیِ کاربر تغییرنام‌داده برگشته است")
    assert 'record.get("reason")' not in lane
