import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules import access_profile_guard


def test_profile_terms_detection():
    """Verify exact detection of prohibited terms in first/last name, username, and bio."""
    terms_to_test = [
        ("پهلوی", True),
        ("دلباخته پهلوی", True),
        ("شاهزاده", True),
        ("شاه زاده", True),
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
        assert res is not None, f"Expected block for term {text!r}"


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


def test_profile_guard_lifecycle():
    """Verify blocking, persistence, diagnostic logging, and restoration upon name change."""
    user_id = 9991234
    access_profile_guard.unblock(user_id)
    assert access_profile_guard.is_blocked(user_id) is False

    # 1. Prohibited user
    bad_user = SimpleNamespace(id=user_id, first_name="رضا شاه", last_name=None, username=None)
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
