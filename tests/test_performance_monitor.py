"""Offline tests for owner-only, non-blocking slow-process monitoring.

    python3 tests/test_performance_monitor.py
"""
import asyncio
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import performance_monitor as monitoring


class Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def log_info(self, message):
        self.infos.append(message)

    def log_error(self, message):
        self.errors.append(message)


class PeerUser:
    def __init__(self, user_id):
        self.user_id = user_id


class PeerChannel:
    def __init__(self, channel_id):
        self.channel_id = channel_id


class FakeClient:
    def __init__(self, owner_id, *, delay=0.0, group_target=False):
        self.owner_id = owner_id
        self.delay = delay
        self.group_target = group_target
        self.resolved = []
        self.sent = []

    async def get_input_entity(self, owner_id):
        self.resolved.append(owner_id)
        if self.group_target:
            return PeerChannel(owner_id)
        return PeerUser(owner_id)

    async def send_message(self, target, text):
        if self.delay:
            await asyncio.sleep(self.delay)
        self.sent.append((target, text))
        return {"id": len(self.sent)}


class SlowProcessMonitorTests(unittest.TestCase):
    def setUp(self):
        self.owner_id = 876543210
        self.original_get_owner = monitoring.get_owner
        self.original_is_global_owner = monitoring.is_global_owner
        monitoring.get_owner = lambda: {
            "user_id": self.owner_id,
            "username": None,
        }
        monitoring.is_global_owner = (
            lambda value: int(getattr(value, "id", value)) == self.owner_id
        )

    def tearDown(self):
        monitoring.get_owner = self.original_get_owner
        monitoring.is_global_owner = self.original_is_global_owner

    def test_at_or_below_150ms_never_logs_or_sends(self):
        async def scenario(state_file):
            logger = Logger()
            client = FakeClient(self.owner_id)
            monitor = monitoring.SlowProcessMonitor(
                client,
                logger,
                cooldown_seconds=0,
                global_min_interval_seconds=0,
                state_path=state_file,
            )
            monitor.start()
            self.assertFalse(monitor.record(
                total_ms=149.9,
                chat_id=1,
                message_id=10,
                handler="normal_handler",
            ))
            self.assertFalse(monitor.record(
                total_ms=150.0,
                chat_id=1,
                message_id=11,
                handler="normal_handler",
            ))
            await asyncio.sleep(0)
            await monitor.close()
            return logger, client

        with tempfile.TemporaryDirectory() as directory:
            logger, client = asyncio.run(scenario(
                Path(directory) / "performance_state.json"
            ))
        self.assertEqual(client.sent, [])
        self.assertFalse(any("SLOW_PROCESS" in row for row in logger.infos))

    def test_slow_report_is_non_blocking_and_owner_only(self):
        async def scenario(state_file):
            logger = Logger()
            client = FakeClient(self.owner_id, delay=0.15)
            monitor = monitoring.SlowProcessMonitor(
                client,
                logger,
                cooldown_seconds=600,
                global_min_interval_seconds=0,
                state_path=state_file,
            )
            monitor.start()
            started = time.perf_counter()
            queued = monitor.record(
                total_ms=185.4,
                chat_id=-10077,
                message_id=42,
                handler="process_incoming_message",
                timestamp="2026-08-21T22:00:00+03:30",
            )
            record_ms = (time.perf_counter() - started) * 1000
            self.assertTrue(queued)
            self.assertLess(record_ms, 25.0)
            # Network delivery is still sleeping; record() did not await it.
            self.assertEqual(client.sent, [])
            await monitor.queue.join()
            await monitor.close()
            return logger, client

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger, client = asyncio.run(scenario(
                root / "performance_state.json"
            ))
            self.assertFalse((root / "watchdog_pending.json").exists())

        self.assertEqual(client.resolved, [self.owner_id])
        self.assertEqual(len(client.sent), 1)
        target, report = client.sent[0]
        self.assertIsInstance(target, PeerUser)
        self.assertEqual(target.user_id, self.owner_id)
        self.assertIn("نوع: SLOW_PROCESS", report)
        self.assertIn("زمان کل پردازش: 185.4 ms", report)
        self.assertIn("chat_id: -10077", report)
        self.assertIn("message_id: 42", report)
        self.assertIn("handler: process_incoming_message", report)
        self.assertIn("timestamp: 2026-08-21T22:00:00+03:30", report)
        self.assertTrue(any(
            row.startswith("SLOW_PROCESS total_ms=185.4")
            for row in logger.infos
        ))

    def test_same_handler_and_chat_are_deduplicated(self):
        async def scenario(state_file):
            logger = Logger()
            client = FakeClient(self.owner_id)
            monitor = monitoring.SlowProcessMonitor(
                client,
                logger,
                cooldown_seconds=600,
                global_min_interval_seconds=0,
                state_path=state_file,
            )
            monitor.start()
            now = time.time()
            self.assertTrue(monitor.record(
                total_ms=180,
                chat_id=55,
                message_id=1,
                handler="process_priority_command",
                now_epoch=now,
            ))
            self.assertFalse(monitor.record(
                total_ms=220,
                chat_id=55,
                message_id=2,
                handler="process_priority_command",
                now_epoch=now + 1,
            ))
            await monitor.queue.join()
            self.assertFalse(monitor.record(
                total_ms=250,
                chat_id=55,
                message_id=3,
                handler="process_priority_command",
                now_epoch=now + 2,
            ))
            await monitor.close()
            return logger, client

        with tempfile.TemporaryDirectory() as directory:
            logger, client = asyncio.run(scenario(
                Path(directory) / "performance_state.json"
            ))
        self.assertEqual(len(client.sent), 1)
        # All slow occurrences are still available in local performance logs.
        slow_lines = [
            row for row in logger.infos
            if row.startswith("SLOW_PROCESS total_ms=")
        ]
        self.assertEqual(len(slow_lines), 3)

    def test_cooldown_survives_monitor_restart(self):
        async def scenario(state_file):
            now = time.time()
            first_client = FakeClient(self.owner_id)
            first = monitoring.SlowProcessMonitor(
                first_client,
                Logger(),
                cooldown_seconds=600,
                global_min_interval_seconds=0,
                state_path=state_file,
            )
            first.start()
            self.assertTrue(first.record(
                total_ms=175,
                chat_id=808,
                message_id=1,
                handler="persistent_handler",
                now_epoch=now,
            ))
            await first.queue.join()
            await first.close()

            second_client = FakeClient(self.owner_id)
            second = monitoring.SlowProcessMonitor(
                second_client,
                Logger(),
                cooldown_seconds=600,
                global_min_interval_seconds=0,
                state_path=state_file,
            )
            second.start()
            self.assertFalse(second.record(
                total_ms=190,
                chat_id=808,
                message_id=2,
                handler="persistent_handler",
                now_epoch=now + 5,
            ))
            await second.close()
            return first_client, second_client

        with tempfile.TemporaryDirectory() as directory:
            first_client, second_client = asyncio.run(scenario(
                Path(directory) / "performance_state.json"
            ))
        self.assertEqual(len(first_client.sent), 1)
        self.assertEqual(second_client.sent, [])

    def test_group_peer_is_rejected_before_slow_report_send(self):
        async def scenario(state_file):
            logger = Logger()
            client = FakeClient(self.owner_id, group_target=True)
            monitor = monitoring.SlowProcessMonitor(
                client,
                logger,
                cooldown_seconds=0,
                global_min_interval_seconds=0,
                state_path=state_file,
            )
            monitor.start()
            self.assertTrue(monitor.record(
                total_ms=151,
                chat_id=5,
                message_id=9,
                handler="group_target_test",
            ))
            await monitor.queue.join()
            await monitor.close()
            return logger, client

        with tempfile.TemporaryDirectory() as directory:
            logger, client = asyncio.run(scenario(
                Path(directory) / "performance_state.json"
            ))
        self.assertEqual(client.sent, [])
        self.assertTrue(any(
            "SLOW_PROCESS OWNER REPORT FAILED" in row
            for row in logger.errors
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
