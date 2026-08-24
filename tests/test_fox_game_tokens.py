import asyncio
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import economy
from modules import fox_game_tokens, group_storage
from handlers.message_handler import handle_new_message


class MockEvent:
    def __init__(self, text, chat_id=5001, user_id=9001, first_name="علی"):
        self.raw_text = text
        self.message = SimpleNamespace(message=text, id=1, entities=None)
        self.chat_id = chat_id
        self.sender_id = user_id
        self.is_private = False
        self.sender = SimpleNamespace(
            id=user_id,
            first_name=first_name,
            last_name=None,
            username="ali_test",
        )
        self.replies = []

    async def reply(self, msg, *args, **kwargs):
        self.replies.append(msg)
        return SimpleNamespace(id=len(self.replies))

    async def get_sender(self):
        return self.sender

    async def get_chat(self):
        return SimpleNamespace(id=self.chat_id)


def test_token_creation_and_device_binding():
    """Verify exclusive token creation, group binding, and device binding protection."""
    chat_id = "test_chat_1"
    user_id = "user_8899"

    # Activate group first
    group_storage.activate_group(chat_id, "گروه تستی شماره ۱")

    # Create token
    token = fox_game_tokens.create_token(chat_id, user_id, "کاربر تستی")
    assert token is not None
    assert len(token) >= 32

    # First device validates token -> Success and bound
    device_a = "device_fingerprint_alpha"
    valid, record, err = fox_game_tokens.validate_token(token, device_a)
    assert valid is True
    assert record["user_id"] == user_id
    assert record["chat_id"] == chat_id
    assert record["device_id"] == device_a

    # Second device tries to use the same token -> Access denied
    device_b = "device_fingerprint_beta"
    valid_b, record_b, err_b = fox_game_tokens.validate_token(token, device_b)
    assert valid_b is False
    assert "مخصوص کاربر و دستگاه دیگری است" in err_b


def test_token_group_binding_and_deactivation():
    """Verify tokens are strictly tied to active groups and revoked when group is deactivated."""
    chat_id = "test_group_bind_99"
    user_id = "user_bind_11"
    device_id = "dev_bind_alpha"

    # 1. Activate group
    group_storage.activate_group(chat_id, "گروه تست وابستگی")
    token = fox_game_tokens.create_token(chat_id, user_id, "کاربر تست وابستگی")

    # 2. Token should be valid in active group
    valid, record, err = fox_game_tokens.validate_token(token, device_id)
    assert valid is True
    assert record["chat_id"] == chat_id

    # 3. Token cannot be validated against a different expected group
    valid_diff, _, err_diff = fox_game_tokens.validate_token(token, device_id, expected_chat_id="other_group_88")
    assert valid_diff is False
    assert "برای این گروه صادر نشده است" in err_diff

    # 4. Deactivate group -> Token must immediately fail and be revoked
    group_storage.deactivate_group(chat_id, "گروه تست وابستگی")
    valid_after, _, err_after = fox_game_tokens.validate_token(token, device_id)
    assert valid_after is False
    assert "معتبر نیست" in err_after or "فعال نیست" in err_after or "منقضی" in err_after


def test_token_expiration():
    """Verify expired tokens are rejected."""
    chat_id = "test_chat_2"
    user_id = "user_7766"

    group_storage.activate_group(chat_id, "گروه تستی ۲")
    token = fox_game_tokens.create_token(chat_id, user_id, "منقضی")
    # Manually expire
    data = fox_game_tokens._load_json(fox_game_tokens.TOKEN_FILE)
    data[token]["expires_at"] = time.time() - 10
    fox_game_tokens._save_json(fox_game_tokens.TOKEN_FILE, data)

    valid, record, err = fox_game_tokens.validate_token(token, "dev_1")
    assert valid is False
    assert "منقضی" in err or "پایان رسیده" in err


def make_mock_bot():
    return SimpleNamespace(
        client=MagicMock(),
        logger=MagicMock(),
        tracker=MagicMock(get_count=lambda c, u: 0),
        punished_users=set(),
        spam_burst_users=set(),
        spam_lock=set(),
        is_spam_locked=lambda k: False,
        config_manager=SimpleNamespace(get=lambda k, d=None: d),
    )


def test_bot_command_site_group_inactive():
    """Verify bot replies with inactive group warning if bot is not activated in group."""
    async def scenario():
        chat_id = 6099
        user_id = 9099

        # Ensure group is inactive
        group_storage.deactivate_group(chat_id, "گروه غیرفعال")

        bot = make_mock_bot()
        event = MockEvent("سایت بازی", chat_id=chat_id, user_id=user_id)
        await handle_new_message(bot, event)

        assert len(event.replies) == 1
        assert "روباه در این گروه فعال نیست" in event.replies[0]

    asyncio.run(scenario())


def test_bot_command_site_insufficient_balance():
    """Verify bot replies with insufficient balance warning when bronze < 30 in active group."""
    async def scenario():
        chat_id = 6001
        user_id = 9002

        group_storage.activate_group(chat_id, "گروه تستی ۳")

        # Reset balance
        b = economy.get_balance(chat_id, user_id)
        if b.get(economy.BRONZE, 0) > 0:
            economy.remove_bronze(chat_id, user_id, b.get(economy.BRONZE, 0))

        bot = make_mock_bot()

        event = MockEvent("سایت بازی", chat_id=chat_id, user_id=user_id)
        await handle_new_message(bot, event)

        assert len(event.replies) == 1
        assert "موجودی کافی نیست" in event.replies[0]
        assert "حداقل ۳۰ برنز" in event.replies[0]

    asyncio.run(scenario())


def test_bot_command_site_successful_deduction_and_link():
    """Verify bot deducts 30 bronze and returns exclusive token link when bronze >= 30."""
    async def scenario():
        chat_id = 6002
        user_id = 9003

        group_storage.activate_group(chat_id, "گروه تستی ۴")

        # Reset and add 50 bronze
        b_before = economy.get_balance(chat_id, user_id).get(economy.BRONZE, 0)
        if b_before > 0:
            economy.remove_bronze(chat_id, user_id, b_before)
        economy.add_bronze(chat_id, user_id, 50, note="شارژ تست")

        bot = make_mock_bot()

        event = MockEvent("سایت بازی", chat_id=chat_id, user_id=user_id, first_name="رضا")
        await handle_new_message(bot, event)

        assert len(event.replies) == 1
        reply = event.replies[0]
        assert "وارد سایت شوید" in reply
        assert "token=" in reply
        assert "۲۴ ساعت" in reply

        # Check balance after deduction
        b = economy.get_balance(chat_id, user_id)
        assert b.get(economy.BRONZE, 0) == 20  # 50 - 30 = 20

    asyncio.run(scenario())


def test_user_data_and_leaderboard_persistence_across_new_tokens():
    """Verify that user progress, nickname, wins, and coins persist when new tokens are generated or after group reactivation."""
    unique_suffix = str(int(time.time() * 1000))
    chat_id = f"test_chat_persist_{unique_suffix}"
    user_id = f"user_permanent_{unique_suffix}"
    device_id = f"dev_persist_{unique_suffix}"

    group_storage.activate_group(chat_id, "گروه پایداری داده")

    # 1. Create first token & play
    token1 = fox_game_tokens.create_token(chat_id, user_id, "کاربر تستی")
    fox_game_tokens.update_nickname(token1, "قهرمان همیشگی روباه", device_id)
    fox_game_tokens.record_win(token1, "رمز مخفی", bronze_won=100, silver_won=10, gold_won=5, device_id=device_id)

    # 2. Group gets deactivated (e.g. expired or bot removed) -> Token 1 is revoked
    group_storage.deactivate_group(chat_id, "گروه پایداری داده")
    valid_old, _, _ = fox_game_tokens.validate_token(token1, device_id)
    assert valid_old is False

    # 3. Leaderboard data is STILL preserved
    lb = fox_game_tokens.get_real_leaderboard()
    player = next((p for p in lb if p["user_id"] == user_id), None)
    assert player is not None
    assert player["nickname"] == "قهرمان همیشگی روباه"
    assert player["wins"] == 1
    assert player["gold_won"] == 5

    # 4. Group is reactivated -> User gets a brand new token
    group_storage.activate_group(chat_id, "گروه پایداری داده")
    token2 = fox_game_tokens.create_token(chat_id, user_id, "نام جدید از تلگرام")

    # 5. Token 2 must automatically preserve previous custom nickname and stats
    valid_new, record_new, _ = fox_game_tokens.validate_token(token2, device_id)
    assert valid_new is True
    assert record_new["nickname"] == "قهرمان همیشگی روباه"

    # 6. Additional wins increment existing stats seamlessly
    fox_game_tokens.record_win(token2, "تک‌تیرانداز روباه", bronze_won=2, silver_won=0, gold_won=0, device_id=device_id)
    lb_after = fox_game_tokens.get_real_leaderboard()
    player_after = next((p for p in lb_after if p["user_id"] == user_id), None)
    assert player_after["wins"] == 2
    assert player_after["bronze_won"] == 102
    assert player_after["gold_won"] == 5


def test_nickname_update_and_real_leaderboard():
    """Verify player nickname updates and real leaderboard ranking."""
    chat_id = "test_chat_3"
    user_id = "user_5544"

    group_storage.activate_group(chat_id, "گروه تستی ۵")
    token = fox_game_tokens.create_token(chat_id, user_id, "روباه اولیه")
    device_id = "dev_real_test"

    # 1. Update nickname
    ok, new_name = fox_game_tokens.update_nickname(token, "سلطان روباه ۷۷", device_id)
    assert ok is True
    assert new_name == "سلطان روباه ۷۷"

    # 2. Record game wins
    fox_game_tokens.record_win(token, "رمز مخفی", bronze_won=100, silver_won=0, gold_won=15, device_id=device_id)

    # 3. Check real leaderboard
    lb = fox_game_tokens.get_real_leaderboard()
    assert len(lb) >= 1
    found = next((p for p in lb if p["user_id"] == user_id), None)
    assert found is not None
    assert found["nickname"] == "سلطان روباه ۷۷"
    assert found["wins"] >= 1
    assert found["gold_won"] >= 15
    assert found["bronze_won"] >= 100
