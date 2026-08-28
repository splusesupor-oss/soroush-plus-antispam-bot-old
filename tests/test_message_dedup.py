"""Group message_id dedup: one chat event cannot produce two replies."""
import asyncio
import threading
from types import SimpleNamespace

from modules import message_dedup as dedup
from modules.simple_replies import SIMPLE_REPLIES
from modules.group_memory import friendly_reply
from modules.group_dispatch import classify_priority
from handlers.private_handler import is_private_event, try_handle_private_start


def setup_function():
    dedup.reset()


def test_normal_message_accepted_once():
    assert dedup.begin(-1001, 10) is True
    dedup.finish(-1001, 10)
    assert dedup.begin(-1001, 10) is False


def test_bot_call_same_message_id_second_is_duplicate():
    assert classify_priority("ربات")[1] == "command"
    assert SIMPLE_REPLIES.get("ربات")
    first = dedup.begin(-1002, 77)
    dedup.finish(-1002, 77)
    second = dedup.begin(-1002, 77)
    assert first is True
    assert second is False


def test_same_text_different_message_ids_both_run():
    assert dedup.begin(-1003, 1) is True
    dedup.finish(-1003, 1)
    assert dedup.begin(-1003, 2) is True
    dedup.finish(-1003, 2)


def test_same_message_id_different_chats_both_run():
    assert dedup.begin(-11, 5) is True
    dedup.finish(-11, 5)
    assert dedup.begin(-22, 5) is True
    dedup.finish(-22, 5)


def test_in_flight_blocks_duplicate_before_finish():
    assert dedup.begin(-1004, 9) is True
    assert dedup.begin(-1004, 9) is False
    dedup.finish(-1004, 9)
    assert dedup.begin(-1004, 9) is False


def test_reconnect_replay_same_id_is_skipped():
    assert dedup.begin(-1005, 42) is True
    dedup.finish(-1005, 42)
    # Same process after reconnect: seen set still holds the id.
    assert dedup.begin(-1005, 42) is False


def test_missing_ids_are_not_dropped():
    assert dedup.begin(None, 1) is True
    assert dedup.begin(-1006, None) is True
    assert dedup.begin(None, None) is True


def test_pv_not_classified_as_group_dedup_target():
    event = SimpleNamespace(
        is_private=True,
        chat_id=68074059,
        message=SimpleNamespace(message="/start", id=3),
    )
    assert is_private_event(event) is True
    group = SimpleNamespace(
        is_private=False,
        chat_id=-1000023164149,
        message=SimpleNamespace(message="ربات", id=3),
    )
    assert is_private_event(group) is False


def test_two_routes_same_id_only_one_reply():
    replies = []

    def handle_once(chat_id, message_id, text):
        if not dedup.begin(chat_id, message_id):
            return False
        try:
            replies.append(SIMPLE_REPLIES.get(text) or friendly_reply("علی", text))
            return True
        finally:
            dedup.finish(chat_id, message_id)

    assert handle_once(-7, 15, "ربات") is True
    assert handle_once(-7, 15, "ربات") is False
    assert len(replies) == 1
    assert "جانم" in replies[0]


def test_concurrent_same_id_only_one_winner():
    wins = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        if dedup.begin(-8, 99):
            wins.append(1)
            dedup.finish(-8, 99)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(wins) == 1


def test_private_start_still_runs_without_dedup():
    class Event:
        def __init__(self):
            self.is_private = True
            self.chat_id = 12345
            self.message = SimpleNamespace(message="/start", id=1)
            self.replies = []

        async def reply(self, text, **kwargs):
            self.replies.append(text)

    bot = SimpleNamespace(logger=SimpleNamespace(log_info=lambda *a, **k: None, log_error=lambda *a, **k: None), client=None)
    event = Event()
    handled = asyncio.run(try_handle_private_start(bot, event))
    assert handled is True
    assert event.replies
