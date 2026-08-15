import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import handlers.message_handler as handler


class _Logger:
    def log_info(self, _message):
        pass

    def log_error(self, message):
        raise AssertionError(message)


def test_big_incident_drains_ids_captured_during_cleanup(monkeypatch):
    bot = SimpleNamespace(logger=_Logger(), _big_spam_incidents={})
    chat_id, user_id = -90001, 73
    incident = handler._big_spam_incident(bot, (chat_id, user_id), {101})
    batches = []

    async def fake_cleanup(_bot, _chat_id, _user_id, ids):
        batches.append(set(ids))
        if len(batches) == 1:
            # Simulate an in-flight incoming message while the first batch is
            # being deleted. It must be picked up before the incident ends.
            handler._capture_big_spam_message(bot, chat_id, user_id, 102)
        return len(ids), []

    sent = []

    async def fake_notice(_bot, _event, _chat_id, _user_id, count, _notice_id):
        sent.append(count)
        return True

    monkeypatch.setattr(handler, "cleanup_spam_messages", fake_cleanup)
    monkeypatch.setattr(handler, "_send_spam_ban_cleanup_notification", fake_notice)

    async def run():
        await handler._drain_big_spam_incident(
            bot, SimpleNamespace(sender=None), chat_id, user_id, incident
        )
        pending = [
            task for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        ]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    asyncio.run(run())

    assert batches == [{101}, {102}]
    assert sent == [2]
    assert (chat_id, user_id) not in bot._big_spam_incidents


def test_big_incident_retries_remaining_ids(monkeypatch):
    bot = SimpleNamespace(logger=_Logger(), _big_spam_incidents={})
    chat_id, user_id = -90002, 74
    incident = handler._big_spam_incident(bot, (chat_id, user_id), {201})
    calls = []

    async def fake_cleanup(_bot, _chat_id, _user_id, ids):
        calls.append(set(ids))
        return (0, list(ids)) if len(calls) == 1 else (len(ids), [])

    async def instant_sleep(_seconds):
        return None

    async def fake_notice(*_args):
        return True

    monkeypatch.setattr(handler, "cleanup_spam_messages", fake_cleanup)
    monkeypatch.setattr(handler, "_send_spam_ban_cleanup_notification", fake_notice)
    monkeypatch.setattr(handler._asyncio, "sleep", instant_sleep)

    asyncio.run(handler._drain_big_spam_incident(
        bot, SimpleNamespace(sender=None), chat_id, user_id, incident
    ))

    assert calls == [{201}, {201}]
    assert (chat_id, user_id) not in bot._big_spam_incidents
