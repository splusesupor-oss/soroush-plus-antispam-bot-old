"""Focused no-network regressions for fair global SPlusthon RPC admission."""
import asyncio
from types import SimpleNamespace

from modules.outgoing_sender import (
    _CHAT_GATES,
    _wrap_call_with_gate,
    install as install_outgoing_sender,
)
from modules.outgoing_profiler import _log_rpc_budget
from modules.rpc_governor import (
    P0_CRITICAL,
    P1_DELETE,
    P2_SEND,
    P3_HEAVY,
    RpcAdmission,
    RpcGovernor,
    classify_request,
    is_keepalive_request,
)


def admission(priority, bucket, chat):
    return RpcAdmission(priority, bucket, bucket, str(chat))


def test_request_classification_matches_soroush_workloads():
    class EditBannedRequest:
        pass

    class DeleteMessagesRequest:
        pass

    class SendMessageRequest:
        pass

    class GetParticipantsRequest:
        pass

    assert classify_request(EditBannedRequest()).priority == P0_CRITICAL
    assert classify_request(DeleteMessagesRequest()).priority == P1_DELETE
    assert classify_request(SendMessageRequest()).priority == P2_SEND
    assert classify_request(GetParticipantsRequest()).priority == P3_HEAVY
    assert classify_request(SendMessageRequest(), urgent_send=True).priority == P2_SEND
    assert classify_request(GetParticipantsRequest(), critical_context=True).priority == P3_HEAVY
    assert classify_request(DeleteMessagesRequest(), critical_context=True).priority == P1_DELETE


def test_noncritical_cannot_consume_three_reserved_critical_slots():
    async def scenario():
        governor = RpcGovernor(
            total_limit=8, noncritical_limit=5,
            delete_limit=4, send_limit=3, heavy_limit=1,
        )
        permits = []
        for index in range(3):
            permits.append(await governor.acquire(admission(P2_SEND, "send", index)))
        for index in range(2):
            permits.append(await governor.acquire(admission(P1_DELETE, "delete", index)))

        blocked = asyncio.create_task(
            governor.acquire(admission(P1_DELETE, "delete", "blocked"))
        )
        await asyncio.sleep(0)
        assert not blocked.done()
        assert governor.snapshot()["active_noncritical"] == 5

        critical = await asyncio.wait_for(
            governor.acquire(admission(P0_CRITICAL, "critical", "admin")),
            timeout=0.05,
        )
        assert governor.snapshot()["active"] == 6
        critical.release()
        permits[0].release()
        extra = await asyncio.wait_for(blocked, timeout=0.05)
        extra.release()
        for permit in permits[1:]:
            permit.release()
        assert governor.snapshot()["active"] == 0

    asyncio.run(scenario())


def test_class_caps_limit_deletes_sends_and_heavy_reads_independently():
    async def scenario():
        governor = RpcGovernor(total_limit=8, noncritical_limit=8)
        deletes = [
            await governor.acquire(admission(P1_DELETE, "delete", index))
            for index in range(4)
        ]
        fifth_delete = asyncio.create_task(
            governor.acquire(admission(P1_DELETE, "delete", "fifth"))
        )
        sends = [
            await governor.acquire(admission(P2_SEND, "send", index))
            for index in range(3)
        ]
        fourth_send = asyncio.create_task(
            governor.acquire(admission(P2_SEND, "send", "fourth"))
        )
        heavy = await governor.acquire(admission(P3_HEAVY, "heavy", "one"))
        second_heavy = asyncio.create_task(
            governor.acquire(admission(P3_HEAVY, "heavy", "two"))
        )
        await asyncio.sleep(0)
        assert not fifth_delete.done()
        assert not fourth_send.done()
        assert not second_heavy.done()

        deletes[0].release()
        replacement_delete = await asyncio.wait_for(fifth_delete, timeout=0.05)
        sends[0].release()
        replacement_send = await asyncio.wait_for(fourth_send, timeout=0.05)
        heavy.release()
        replacement_heavy = await asyncio.wait_for(second_heavy, timeout=0.05)

        for permit in deletes[1:] + sends[1:]:
            permit.release()
        replacement_delete.release()
        replacement_send.release()
        replacement_heavy.release()
        assert governor.snapshot()["active"] == 0

    asyncio.run(scenario())


def test_round_robin_prevents_one_chat_from_monopolizing_a_class():
    async def scenario():
        governor = RpcGovernor(
            total_limit=1, noncritical_limit=1, send_limit=1
        )
        holder = await governor.acquire(admission(P2_SEND, "send", "holder"))
        order = []

        async def run(label, chat):
            permit = await governor.acquire(admission(P2_SEND, "send", chat))
            order.append(label)
            permit.release()

        tasks = [
            asyncio.create_task(run("A1", "A")),
            asyncio.create_task(run("A2", "A")),
            asyncio.create_task(run("B1", "B")),
        ]
        await asyncio.sleep(0)
        holder.release()
        await asyncio.gather(*tasks)
        return order, governor.snapshot()

    order, snapshot = asyncio.run(scenario())
    assert order == ["A1", "B1", "A2"]
    assert snapshot["active"] == 0
    assert snapshot["waiting"] == 0


def test_cancelled_waiter_never_leaks_a_permit():
    async def scenario():
        governor = RpcGovernor(total_limit=1, noncritical_limit=1)
        holder = await governor.acquire(admission(P2_SEND, "other", "holder"))
        waiter = asyncio.create_task(
            governor.acquire(admission(P2_SEND, "other", "cancel"))
        )
        await asyncio.sleep(0)
        waiter.cancel()
        result = await asyncio.gather(waiter, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
        holder.release()
        permit = await asyncio.wait_for(
            governor.acquire(admission(P2_SEND, "other", "after")),
            timeout=0.05,
        )
        permit.release()
        return governor.snapshot()

    snapshot = asyncio.run(scenario())
    assert snapshot["active"] == 0
    assert snapshot["waiting"] == 0
    assert snapshot["stats"]["cancelled_waiters"] == 1


def test_shadow_mode_observes_without_blocking():
    async def scenario():
        governor = RpcGovernor(
            total_limit=1, noncritical_limit=1, shadow=True
        )
        first = await governor.acquire(admission(P2_SEND, "other", "A"))
        second = await asyncio.wait_for(
            governor.acquire(admission(P2_SEND, "other", "B")),
            timeout=0.05,
        )
        snapshot = governor.snapshot()
        second.release()
        first.release()
        return snapshot, governor.snapshot()

    during, after = asyncio.run(scenario())
    assert during["active"] == 2
    assert during["stats"]["shadow_would_wait"] == 1
    assert after["active"] == 0


def test_per_chat_low_gate_is_fifo_bounded_and_removed_when_idle():
    class SendMessageRequest:
        def __init__(self, chat_id):
            self.peer = SimpleNamespace(channel_id=chat_id)

    class Client:
        def __init__(self):
            self._sender = object()
            self.release = asyncio.Event()
            self.active = 0
            self.maximum = 0
            self.started = 0

        async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
            self.active += 1
            self.started += 1
            self.maximum = max(self.maximum, self.active)
            try:
                await self.release.wait()
            finally:
                self.active -= 1

    async def scenario():
        _CHAT_GATES.clear()
        client = Client()
        assert _wrap_call_with_gate(client, None, None)
        tasks = [
            asyncio.create_task(
                client._call(client._sender, SendMessageRequest(99))
            )
            for _ in range(5)
        ]
        await asyncio.sleep(0)
        assert client.started == 2
        client.release.set()
        await asyncio.gather(*tasks)
        return client.maximum

    maximum = asyncio.run(scenario())
    assert maximum == 2
    assert _CHAT_GATES == {}


def test_rebuilt_client_reuses_the_same_bot_level_governor():
    class Client:
        def __init__(self):
            self._sender = object()

        async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
            return request

        async def send_message(self, entity, text):
            return text

    bot = SimpleNamespace(logger=None)
    first = Client()
    first_sender = install_outgoing_sender(first, bot, None)
    governor = bot.rpc_governor
    second = Client()
    second_sender = install_outgoing_sender(second, bot, None)

    assert first_sender is not second_sender
    assert first._call._rpc_governor is governor
    assert second._call._rpc_governor is governor


def test_wrapped_exception_and_cancellation_release_all_slots():
    class SendMessageRequest:
        def __init__(self, chat_id):
            self.peer = SimpleNamespace(channel_id=chat_id)

    class Client:
        def __init__(self):
            self._sender = object()
            self.block = asyncio.Event()
            self.fail = True

        async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
            if self.fail:
                raise RuntimeError("flood/retry boundary")
            await self.block.wait()

    async def scenario():
        _CHAT_GATES.clear()
        governor = RpcGovernor(total_limit=2, noncritical_limit=2)
        client = Client()
        assert _wrap_call_with_gate(client, None, governor)
        try:
            await client._call(client._sender, SendMessageRequest(1))
        except RuntimeError:
            pass
        else:
            raise AssertionError("inner error must propagate")
        assert governor.snapshot()["active"] == 0

        client.fail = False
        task = asyncio.create_task(
            client._call(client._sender, SendMessageRequest(2))
        )
        await asyncio.sleep(0)
        assert governor.snapshot()["active"] == 1
        task.cancel()
        result = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
        return governor.snapshot()

    snapshot = asyncio.run(scenario())
    assert snapshot["active"] == 0
    assert snapshot["waiting"] == 0
    assert _CHAT_GATES == {}


def test_governor_wait_is_outside_existing_rpc_timeout_and_finally_releases():
    class SendMessageRequest:
        def __init__(self, chat_id):
            self.peer = SimpleNamespace(channel_id=chat_id)

    class Client:
        def __init__(self):
            self._sender = object()

        async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
            # Models the already-installed inner network timeout. The RPC itself
            # fits; only the outer governor wait makes total wall time longer.
            return await asyncio.wait_for(asyncio.sleep(0.03, result="ok"), 0.05)

    async def scenario():
        _CHAT_GATES.clear()
        governor = RpcGovernor(total_limit=1, noncritical_limit=1)
        holder = await governor.acquire(admission(P2_SEND, "other", "holder"))
        client = Client()
        assert _wrap_call_with_gate(client, None, governor)
        task = asyncio.create_task(
            client._call(client._sender, SendMessageRequest(10))
        )
        await asyncio.sleep(0.07)
        assert not task.done()
        holder.release()
        result = await asyncio.wait_for(task, timeout=0.1)
        snapshot = governor.snapshot()
        return result, snapshot

    result, snapshot = asyncio.run(scenario())
    assert result == "ok"
    assert snapshot["active"] == 0
    assert snapshot["waiting"] == 0
    assert _CHAT_GATES == {}


class _MemLogger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def log_info(self, message):
        self.infos.append(str(message))

    def log_error(self, message):
        self.errors.append(str(message))


def test_ping_keepalive_occupies_critical_if_acquired_directly():
    class PingRequest:
        pass

    class SendMessageRequest:
        pass

    assert is_keepalive_request(PingRequest())
    assert not is_keepalive_request(SendMessageRequest())
    classified = classify_request(PingRequest())
    assert classified.priority == P0_CRITICAL
    assert classified.bucket == "critical"

    async def scenario():
        governor = RpcGovernor(total_limit=2, noncritical_limit=1)
        ping = await governor.acquire(classified)
        snap = governor.snapshot()
        ping.release()
        return snap, governor.snapshot()

    during, after = asyncio.run(scenario())
    assert during["active"] == 1
    assert during["active_by_bucket"].get("critical") == 1
    assert any("PingRequest" in item for item in during["holders"])
    assert after["active"] == 0
    assert after["holders"] == []


def test_governor_blocked_logs_active_limit_and_holders():
    import modules.rpc_governor as rg

    async def scenario():
        old = rg.GOVERNOR_BLOCKED_MS
        rg.GOVERNOR_BLOCKED_MS = 40.0
        logger = _MemLogger()
        try:
            governor = RpcGovernor(
                total_limit=1, noncritical_limit=1, logger=logger
            )
            holder = await governor.acquire(admission(P2_SEND, "send", "busy"))
            snap = governor.snapshot()
            waiter = asyncio.create_task(
                governor.acquire(admission(P1_DELETE, "delete", "blocked"))
            )
            await asyncio.sleep(0.06)
            assert not waiter.done()
            holder.release()
            permit = await asyncio.wait_for(waiter, timeout=0.2)
            permit.release()
            return snap, logger.errors, logger.infos, governor.snapshot()
        finally:
            rg.GOVERNOR_BLOCKED_MS = old

    snap, errors, infos, after = asyncio.run(scenario())
    blocked = [line for line in errors if line.startswith("GOVERNOR BLOCKED")]
    assert blocked, errors
    text = blocked[0]
    assert "bucket=delete" in text
    assert "request=delete" in text
    assert "wait_ms=" in text
    assert "active=" in text
    assert "limit=" in text
    assert "holders=[" in text
    assert "send:send" in text
    assert snap["holders"]
    assert any("GOVERNOR ACQUIRE" in line for line in infos)
    assert after["active"] == 0
    assert after["holders"] == []


def test_keepalive_ping_bypasses_governor_in_call_wrapper():
    class PingRequest:
        pass

    class SendMessageRequest:
        def __init__(self, chat_id):
            self.peer = SimpleNamespace(channel_id=chat_id)

    class Client:
        def __init__(self):
            self._sender = object()
            self.pings = 0

        async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
            if type(request).__name__ == "PingRequest":
                self.pings += 1
                return "pong"
            return "ok"

    async def scenario():
        _CHAT_GATES.clear()
        governor = RpcGovernor(total_limit=1, noncritical_limit=1)
        holder = await governor.acquire(admission(P2_SEND, "send", "busy"))
        client = Client()
        assert _wrap_call_with_gate(client, None, governor)
        ping = await asyncio.wait_for(
            client._call(client._sender, PingRequest()), timeout=0.05
        )
        snap_during = governor.snapshot()
        send_task = asyncio.create_task(
            client._call(client._sender, SendMessageRequest(1))
        )
        await asyncio.sleep(0)
        send_waiting = not send_task.done()
        holder.release()
        await asyncio.wait_for(send_task, timeout=0.1)
        return ping, snap_during, send_waiting, client.pings, governor.snapshot()

    ping, snap, waiting, pings, after = asyncio.run(scenario())
    assert ping == "pong"
    assert pings == 1
    assert snap["active"] == 1
    assert waiting
    assert after["active"] == 0
    assert after["holders"] == []


def test_total_ms_matches_phase_sum_not_wall_clock():
    logger = _MemLogger()
    started = __import__("time").perf_counter() - 2.5
    phases = {
        "started": started,
        "queue_wait_ms": 10.0,
        "governor_wait_ms": 20.0,
        "sender_wait_ms": 5.0,
        "rpc_await_ms": 15.0,
        "operation": "send_message",
    }
    _log_rpc_budget(logger, None, "send_message", phases)
    assert abs(phases["total_ms"] - 50.0) < 0.01
    assert not any("OUTGOING RPC CRITICAL" in line for line in logger.errors)
