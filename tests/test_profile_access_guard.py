import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules import access_profile_guard
from handlers.message_handler import handle_new_message


class MockEvent:
    def __init__(self, text, user_id=2001, first_name="پهلوی", username=None, is_private=False):
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
        )
        self.replies = []

    async def reply(self, msg, *args, **kwargs):
        self.replies.append(msg)
        return SimpleNamespace(id=len(self.replies))

    async def get_sender(self):
        return self.sender

    async def get_chat(self):
        return SimpleNamespace(id=self.chat_id)


def test_profile_terms_detection():
    """Verify exact and combined/root detection of prohibited terms in first/last name, username, and bio."""
    terms_to_test = [
        ("پهلوی", True),
        ("پهلوی بوی", True),
        ("پهلویبوی", True),
        ("دلباخته پهلوی", True),
        ("دلباخته_پهلوی", True),
        ("پهلوی123", True),
        ("عاشق پهلوی", True),
        ("پهلوی_بوی", True),
        ("شاهزاده", True),
        ("شاه زاده", True),
        ("شاهزاده پهلوی", True),
        ("پرچم آمریکا", True),
        ("آمریکا", True),
        ("شاه", True),
        ("رضا شاه", True),
        ("رضاشاه", True),
        ("محمدرضا شاه", True),
        ("جان فدای میهن", True),
        ("فرزند ایران", True),
    ]
    for text, expected in terms_to_test:
        user = SimpleNamespace(first_name=text, last_name=None, username=None)
        res = access_profile_guard.reason(user)
        assert res is not None, f"Expected block for profile name {text!r}"


def test_profile_terms_no_false_positives():
    """Verify legitimate names containing partial characters are not falsely blocked."""
    legit_names = [
        "شاهین",
        "شهاب",
        "شاهرخ",
        "دانشگاه",
        "علی رضایی",
        "محمد حسینی",
        "سارا احمدی",
    ]
    for name in legit_names:
        user = SimpleNamespace(first_name=name, last_name=None, username=None)
        res = access_profile_guard.reason(user)
        assert res is None, f"Unexpected false positive on {name!r}"


def test_user_with_pahlavi_saying_roobah_or_robot():
    """Verify that a user with name containing 'پهلوی' saying 'ربات' gets the restriction notice and no service."""
    async def scenario():
        user_id = 8881234
        access_profile_guard.unblock(user_id)

        bot = SimpleNamespace(
            logger=MagicMock(),
            tracker=MagicMock(get_count=lambda c, u: 0),
            punished_users=set(),
            is_spam_locked=lambda k: False,
        )

        event = MockEvent("ربات", user_id=user_id, first_name="پهلوی")
        await handle_new_message(bot, event)

        assert access_profile_guard.is_blocked(user_id) is True
        assert len(event.replies) == 1
        assert "دسترسی شما از ربات حذف شد" in event.replies[0]
        assert "جانم" not in event.replies[0]  # Must NOT have sent the normal bot reply!

        # Cleanup
        access_profile_guard.unblock(user_id)

    asyncio.run(scenario())


def test_profile_guard_lifecycle():
    """Verify blocking, persistence, diagnostic logging, and restoration upon name change."""
    user_id = 9991234
    access_profile_guard.unblock(user_id)
    assert access_profile_guard.is_blocked(user_id) is False

    # 1. Prohibited user
    bad_user = SimpleNamespace(id=user_id, first_name="پهلوی_بوی", last_name=None, username=None)
    bad_reason = access_profile_guard.reason(bad_user)
    assert bad_reason is not None

    # Block user
    changed = access_profile_guard.block(user_id, bad_reason)
    assert changed is True
    assert access_profile_guard.is_blocked(user_id) is True
    assert access_profile_guard.record_for(user_id)["reason"] == bad_reason

    # 2. User changes name to clean name
    clean_user = SimpleNamespace(id=user_id, first_name="رضا علوی", last_name=None, username=None)
    clean_reason = access_profile_guard.reason(clean_user)
    assert clean_reason is None

    # Unblock
    restored = access_profile_guard.unblock(user_id)
    assert restored is True
    assert access_profile_guard.is_blocked(user_id) is False
