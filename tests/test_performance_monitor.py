"""Offline tests for silent, aggregated slow-process monitoring."""
import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "splusthon" not in sys.modules:
    splusthon = types.ModuleType("splusthon")
    class PeerUser:
        def __init__(self, user_id): self.user_id = user_id
    class InputPeerUser:
        def __init__(self, user_id, access_hash):
            self.user_id, self.access_hash = user_id, access_hash
    splusthon.types = types.SimpleNamespace(PeerUser=PeerUser, InputPeerUser=InputPeerUser)
    sys.modules["splusthon"] = splusthon

from modules import owner_private
from modules.performance_monitor import SlowProcessMonitor


class Logger:
    def __init__(self): self.infos, self.errors = [], []
    def log_info(self, message): self.infos.append(message)
    def log_error(self, message): self.errors.append(message)


class Peer:
    def __init__(self, user_id): self.user_id = user_id


class Client:
    def __init__(self, owner_id):
        self.owner_id, self.sent, self._sender = owner_id, [], None
    async def get_me(self, input_peer=False): return Peer(self.owner_id)
    async def send_message(self, target, text):
        self.sent.append((target, text))


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.owner_id = 987654321
        self.original = owner_private.get_owner
        owner_private.get_owner = lambda: {"user_id": self.owner_id, "username": None}

    def tearDown(self): owner_private.get_owner = self.original

    def test_routine_event_is_silent_and_only_aggregated(self):
        async def scenario():
            logger, client = Logger(), Client(self.owner_id)
            monitor = SlowProcessMonitor(client, logger, batch_interval_seconds=3600)
            self.assertFalse(monitor.record(total_ms=400, chat_id=1, message_id=2, handler="normal"))
            self.assertEqual(logger.infos, [])
            self.assertEqual(client.sent, [])
            await monitor.flush_batch()
            await monitor.close()
            return client
        client = asyncio.run(scenario())
        self.assertEqual(len(client.sent), 1)
        self.assertIn("گزارش تجمیعی", client.sent[0][1])
        self.assertIn("تعداد=1", client.sent[0][1])

    def test_severe_event_alerts_once_per_30_seconds(self):
        async def scenario():
            logger, client = Logger(), Client(self.owner_id)
            monitor = SlowProcessMonitor(client, logger, alert_interval_seconds=30, batch_interval_seconds=3600)
            self.assertTrue(monitor.record(total_ms=1001, chat_id=1, message_id=2, handler="slow", now_epoch=100))
            self.assertFalse(monitor.record(total_ms=2000, chat_id=1, message_id=3, handler="slow", now_epoch=120))
            await monitor.queue.join()
            await monitor.close()
            return client, logger
        client, logger = asyncio.run(scenario())
        self.assertEqual(len(client.sent), 1)
        self.assertIn("گزارش کندی شدید", client.sent[0][1])
        self.assertEqual(logger.infos, [])

    def test_batch_aggregates_all_same_paths_without_terminal_log_noise(self):
        async def scenario():
            logger, client = Logger(), Client(self.owner_id)
            monitor = SlowProcessMonitor(client, logger, batch_interval_seconds=3600)
            for ms in (200, 600, 900):
                monitor.record(total_ms=ms, chat_id=5, message_id=ms, handler="pipeline")
            await monitor.flush_batch()
            await monitor.close()
            return client, logger
        client, logger = asyncio.run(scenario())
        self.assertEqual(len(client.sent), 1)
        report = client.sent[0][1]
        self.assertIn("تعداد=3", report)
        self.assertIn("بیشینه=900.0ms", report)
        self.assertEqual(logger.infos, [])

    def test_pressure_defers_alert_and_batch(self):
        async def scenario():
            logger, client = Logger(), Client(self.owner_id)
            client._sender = type("Sender", (), {"_pending_state": list(range(8))})()
            monitor = SlowProcessMonitor(client, logger, rpc_pressure_limit=8, batch_interval_seconds=3600)
            self.assertTrue(monitor.record(total_ms=1200, chat_id=1, message_id=2, handler="blocked"))
            await monitor.queue.join()
            self.assertFalse(await monitor.flush_batch())
            await monitor.close()
            return client, logger
        client, logger = asyncio.run(scenario())
        self.assertEqual(client.sent, [])
        self.assertEqual(logger.infos, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
