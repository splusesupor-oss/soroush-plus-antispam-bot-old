import asyncio
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import economy
from modules import fox_game_tokens
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
    """Verify exclusive token creation and device binding protection."""
    chat_id = "test_chat_1"
    user_id = "user_8899"

    # Create token
    token = fox_game_tokens.create_token(chat_id, user_id, "کاربر تستی")
    assert token is not None
    assert len(token) >= 32

    # First device validates token -> Success and bound
    device_a = "device_fingerprint_alpha"
    valid, record, err = fox_game_tokens.validate_token(token, device_a)
    assert valid is True
    assert record["user_id"] == user_id
    assert record["device_id"] == device_a

    # Second device tries to use the same token -> Access denied
    device_b = "device_fingerprint_beta"
    valid_b, record_b, err_b = fox_game_tokens.validate_token(token, device_b)
    assert valid_b is False
    assert "مخصوص کاربر و دستگاه دیگری است" in err_b


def test_token_expiration():
    """Verify expired tokens are rejected."""
    chat_id = "test_chat_2"
    user_id = "user_7766"

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


def test_bot_command_site_insufficient_balance():
    """Verify bot replies with insufficient balance warning when bronze < 30."""
    async def scenario():
        chat_id = 6001
        user_id = 9002

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
        assert "۱۰ دقیقه" in reply

        # Check balance after deduction
        b = economy.get_balance(chat_id, user_id)
        assert b.get(economy.BRONZE, 0) == 20  # 50 - 30 = 20

    asyncio.run(scenario())


def test_nickname_update_and_real_leaderboard():
    """Verify player nickname updates and real leaderboard ranking."""
    chat_id = "test_chat_3"
    user_id = "user_5544"

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
