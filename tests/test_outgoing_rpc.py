"""Sender isolation: slow send_message must not stall delete/ban.

Also: GetUsersRequest 404 is not retried or re-enqueued.
Does not import live SPlusthon network code.
"""
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import outgoing_rpc
from modules.message_delete_queue import MessageDeleteQueue
from modules.outgoing_rpc import (
    PermanentRpcError,
    _PrioritySendQueue,
    cached_invalid_users,
    clear_invalid_user_cache,
    drop_invalid_pending,
    get_users_ids,
    install,
    is_permanent_rpc_error,
    remember_invalid_users,
    request_priority,
    unwrap_request,
)

PASSED = FAILED = 0


def check(name, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"FAIL  {name} {detail}")


class Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def log_info(self, message):
        self.infos.append(message)

    def log_error(self, message):
        self.errors.append(message)


class InputUser:
    def __init__(self, user_id, access_hash=0):
        self.user_id = user_id
        self.access_hash = access_hash


class GetUsersRequest:
    def __init__(self, ids):
        self.id = ids


class SendMessageRequest:
    def __init__(self, peer=None, message=""):
        self.peer = peer
        self.message = message


class DeleteMessagesRequest:
    def __init__(self, ids=None):
        self.ids = ids or []


class InvokeWithoutUpdatesRequest:
    def __init__(self, query):
        self.query = query


class NotFoundError(Exception):
    code = 404
    message = "NOT_FOUND"

    def __init__(self, request=None, message="NOT_FOUND", code=404):
        super().__init__(f"RPCError {code}: {message}")
        self.request = request
        self.code = code
        self.message = message


class TimedOutError(Exception):
    code = 503


class RequestState:
    def __init__(self, request):
        self.request = request
        self.future = asyncio.get_event_loop().create_future()


class FakeSender:
    def __init__(self):
        self._pending_state = {}
        self._send_queue = FakePacker()
        self.reconnects = 0

    async def _reconnect(self, last_error):
        self.reconnects += 1
        self._send_queue.extend(list(self._pending_state.values()))
        self._pending_state.clear()
        return "reconnected"


class FakePacker:
    def __init__(self):
        from collections import deque
        self._deque = deque()
        self._ready = asyncio.Event()

    def append(self, state):
        self._deque.append(state)
        self._ready.set()

    def extend(self, states):
        self._deque.extend(states)
        self._ready.set()


class FakeClient:
    def __init__(self, send_ms=80, fail_get_users=False):
        self.send_ms = send_ms
        self.fail_get_users = fail_get_users
        self.calls = []
        self.started = []
        self._sender = FakeSender()
        self._inflight = 0
        self.max_low_inflight = 0

    async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
        name = type(outgoing_rpc.unwrap_request(request)).__name__
        self.calls.append(name)
        self.started.append((name, time.perf_counter()))
        if name == "GetUsersRequest":
            if self.fail_get_users:
                raise NotFoundError(request=request)
            await asyncio.sleep(0.01)
            return [object()]
        if name == "SendMessageRequest":
            self._inflight += 1
            self.max_low_inflight = max(self.max_low_inflight, self._inflight)
            try:
                await asyncio.sleep(self.send_ms / 1000.0)
                return "sent"
            finally:
                self._inflight -= 1
        if name == "DeleteMessagesRequest":
            await asyncio.sleep(0.01)
            return "deleted"
        await asyncio.sleep(0.01)
        return "ok"

    async def send_message(self, entity, message, **kwargs):
        return await self._call(self._sender, SendMessageRequest(entity, message))

    async def delete_messages(self, entity, ids, **kwargs):
        if self.fail_get_users:
            await self._call(self._sender, GetUsersRequest([InputUser(entity)]))
        return await self._call(self._sender, DeleteMessagesRequest(ids))

    async def edit_permissions(self, *args, **kwargs):
        return await self._call(self._sender, type("EditBannedRequest", (), {})())

    async def connect(self):
        return True


def test_classify_and_unwrap():
    print("\n### طبقه‌بندی درخواست و unwrap")
    inner = SendMessageRequest()
    wrapped = InvokeWithoutUpdatesRequest(inner)
    check("unwrap پوست Invoke را می‌کند", unwrap_request(wrapped) is inner)
    check("send_message اولویت پایین است", request_priority(inner) == "low")
    check("delete اولویت بالا است",
          request_priority(DeleteMessagesRequest()) == "high")
    check("GetUsers عادی است", request_priority(GetUsersRequest([])) == "normal")
    ids = get_users_ids(GetUsersRequest([InputUser(42), InputUser(7)]))
    check("شناسه GetUsers خوانده می‌شود", ids == (42, 7), f"-> {ids}")


def test_permanent_matcher():
    print("\n### خطای دائمی در برابر موقت")
    check("404 NotFound دائمی است", is_permanent_rpc_error(NotFoundError()))
    check("متن NOT_FOUND دائمی است",
          is_permanent_rpc_error(Exception("RPCError 404: NOT_FOUND")))
    check("timeout دائمی نیست", not is_permanent_rpc_error(TimedOutError()))
    check("ConnectionError دائمی نیست",
          not is_permanent_rpc_error(ConnectionError("reset")))


def test_get_users_404_not_resent():
    print("\n### GetUsers 404 دوباره وارد صف نمی‌شود")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient(fail_get_users=True)
        install(client, logger)
        first = None
        try:
            await client._call(client._sender, GetUsersRequest([InputUser(99)]))
        except NotFoundError as error:
            first = error
        second = None
        try:
            await client._call(client._sender, GetUsersRequest([InputUser(99)]))
        except PermanentRpcError as error:
            second = error
        return first, second, client.calls, logger

    first, second, calls, logger = asyncio.run(scenario())
    check("اولین بار 404 از شبکه آمد", isinstance(first, NotFoundError))
    check("بار دوم بدون ارسال خطا داد", isinstance(second, PermanentRpcError))
    check("GetUsers فقط یک بار ارسال شد", calls.count("GetUsersRequest") == 1,
          f"-> {calls}")
    check("کش پر شد", cached_invalid_users(GetUsersRequest([InputUser(99)])) == (99,))
    check("لاگ DROP ثبت شد",
          any("OUTGOING RPC DROP" in line for line in logger.infos),
          f"-> {logger.infos}")


def test_reconnect_does_not_requeue_404():
    print("\n### reconnect همان GetUsers 404 را دوباره نمی‌فرستد")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient()
        install(client, logger)
        request = GetUsersRequest([InputUser(55)])
        remember_invalid_users(request, NotFoundError())
        state = RequestState(request)
        client._sender._pending_state[1] = state
        dropped = drop_invalid_pending(client._sender, logger)
        await client._sender._reconnect("net")
        return dropped, list(client._sender._send_queue._deque), state.future

    dropped, queued, future = asyncio.run(scenario())
    check("از pending حذف شد", dropped == 1, f"-> {dropped}")
    check("به صف ارسال برنگشت", queued == [], f"-> {queued}")
    check("future با خطای دائمی بسته شد",
          future.done() and isinstance(future.exception(), PermanentRpcError))


def test_slow_send_does_not_block_delete():
    print("\n### send کند، delete را معطل نمی‌کند")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient(send_ms=200)
        install(client, logger)
        marks = {}

        async def send():
            marks["send_start"] = time.perf_counter()
            await client._call(client._sender, SendMessageRequest(-1, "hi"))
            marks["send_end"] = time.perf_counter()

        async def delete():
            await asyncio.sleep(0.03)
            marks["delete_start"] = time.perf_counter()
            await client.delete_messages(-1, [1, 2])
            marks["delete_end"] = time.perf_counter()

        await asyncio.gather(send(), delete())
        return marks, client.max_low_inflight, logger

    marks, max_low, logger = asyncio.run(scenario())
    delete_during_send = marks["delete_end"] < marks["send_end"]
    delete_wait = (marks["delete_end"] - marks["delete_start"]) * 1000
    print(f"    delete_ms={delete_wait:.1f} max_low={max_low}")
    check("delete قبل از پایان send تمام شد", delete_during_send,
          f"-> send_end-delete_end={(marks['send_end']-marks['delete_end'])*1000:.1f}ms")
    check("delete خودش معطل send نشد", delete_wait < 80, f"-> {delete_wait:.1f}ms")
    check("حداکثر یک send همزمان", max_low == 1, f"-> {max_low}")


def test_second_send_waits_first_but_delete_does_not():
    print("\n### سقف inflight فقط روی send است")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient(send_ms=150)
        install(client, logger)
        marks = {}

        async def send(tag):
            marks[f"{tag}_start"] = time.perf_counter()
            await client._call(client._sender, SendMessageRequest(-2, tag))
            marks[f"{tag}_end"] = time.perf_counter()

        async def delete():
            await asyncio.sleep(0.02)
            marks["d_start"] = time.perf_counter()
            await client._call(client._sender, DeleteMessagesRequest([9]))
            marks["d_end"] = time.perf_counter()

        await asyncio.gather(send("a"), send("b"), delete())
        return marks, client.max_low_inflight, client.started

    marks, max_low, started = asyncio.run(scenario())
    send_started = [stamp for name, stamp in started if name == "SendMessageRequest"]
    send_started.sort()
    gap = None
    if len(send_started) >= 2:
        gap = (send_started[1] - send_started[0]) * 1000
    delete_ms = (marks["d_end"] - marks["d_start"]) * 1000
    print(f"    send_start_gap_ms={gap} delete_ms={delete_ms:.1f} max_low={max_low}")
    check("send دوم بعد از شروع اول می‌آید (سقف inflight)",
          gap is not None and gap >= 120, f"-> {gap}")
    check("هنوز حداکثر یک send همزمان", max_low == 1, f"-> {max_low}")
    check("delete پشت send دوم نماند", delete_ms < 80, f"-> {delete_ms:.1f}ms")


def test_delete_queue_skips_404_retry():
    print("\n### صف حذف 404 را دوباره تلاش نمی‌کند")
    clear_invalid_user_cache()

    class Client:
        def __init__(self):
            self.calls = 0

        async def delete_messages(self, chat_id, ids):
            self.calls += 1
            raise NotFoundError(message="NOT_FOUND (caused by GetUsersRequest)")

    async def scenario():
        client = Client()
        queue = MessageDeleteQueue(client, Logger(), batch_size=15)
        future = queue.enqueue(-9, [1, 2, 3], priority=1)
        deleted, remaining = await asyncio.wait_for(asyncio.wrap_future(future), 2)
        return deleted, remaining, client.calls

    deleted, remaining, calls = asyncio.run(scenario())
    check("هیچ پیامی حذف نشد", deleted == 0)
    check("شناسه‌ها باقی ماندند", remaining == [1, 2, 3], f"-> {remaining}")
    check("فقط یک RPC رفت نه ۳+۳×۳", calls == 1, f"-> {calls}")


def test_delete_queue_still_retries_timeout():
    print("\n### صف حذف خطای موقت را هنوز retry می‌کند")

    class Client:
        def __init__(self):
            self.calls = 0

        async def delete_messages(self, chat_id, ids):
            self.calls += 1
            if self.calls < 3:
                raise TimedOutError("Timeout")
            return True

    async def scenario():
        client = Client()
        queue = MessageDeleteQueue(client, Logger(), batch_size=15)
        future = queue.enqueue(-8, [10], priority=1)
        deleted, remaining = await asyncio.wait_for(asyncio.wrap_future(future), 2)
        return deleted, remaining, client.calls

    deleted, remaining, calls = asyncio.run(scenario())
    check("بعد از timeout موفق شد", deleted == 1 and remaining == [])
    check("چند تلاش شد", calls == 3, f"-> {calls}")


def test_packer_puts_delete_first():
    print("\n### packer حذف را جلوتر از send می‌گذارد")
    clear_invalid_user_cache()

    async def scenario():
        client = FakeClient()
        install(client, Logger())
        packer = client._sender._send_queue
        send = RequestState(SendMessageRequest(-1, "x"))
        delete = RequestState(DeleteMessagesRequest([1]))
        packer.append(send)
        packer.append(delete)
        return [type(item.request).__name__ for item in packer._deque]

    names = asyncio.run(scenario())
    check("حذف در ابتدای صف است", names[0] == "DeleteMessagesRequest", f"-> {names}")
    check("send بعد از آن است", names[-1] == "SendMessageRequest", f"-> {names}")


def test_install_idempotent():
    client = FakeClient()
    first = install(client, Logger())
    second = install(client, Logger())
    check("نصب اول موفق است", first is True)
    check("نصب دوباره بی‌اثر است", second is False)


class SlottedMessagePacker:
    """همان محدودیت SPlusthon: append روی instance قابل جایگزینی نیست."""

    __slots__ = ("_state", "_deque", "_ready", "_log", "_buffer")

    def __init__(self):
        from collections import deque
        self._state = None
        self._deque = deque()
        self._ready = asyncio.Event()
        self._log = None
        self._buffer = None

    def append(self, state):
        self._deque.append(state)
        self._ready.set()

    def extend(self, states):
        self._deque.extend(states)
        self._ready.set()


def test_slotted_packer_is_not_mutated():
    print("\n### MessagePacker با slots نباید monkey-patch شود")
    packer = SlottedMessagePacker()
    raised = None
    try:
        packer.append = lambda state: None
    except Exception as error:
        raised = error
    check(
        "بازتولید باگ: append روی packer read-only است",
        isinstance(raised, AttributeError) and "append" in str(raised),
        f"-> {raised!r}",
    )

    async def scenario():
        logger = Logger()

        class Sender:
            def __init__(self):
                self._pending_state = {}
                self._send_queue = SlottedMessagePacker()

            async def _reconnect(self, last_error):
                return "ok"

        class Client:
            def __init__(self):
                self._sender = None

            async def _call(self, sender, request, ordered=False,
                            flood_sleep_threshold=None):
                return "ok"

            async def connect(self):
                self._sender = Sender()
                return True

        client = Client()
        install(client, logger)
        await client.connect()
        queue = client._sender._send_queue
        send = RequestState(SendMessageRequest(-1, "x"))
        delete = RequestState(DeleteMessagesRequest([1]))
        queue.append(send)
        queue.append(delete)
        names = [type(item.request).__name__ for item in queue._deque]
        return queue, names, type(client._sender._send_queue._inner).__name__

    queue, names, inner_name = asyncio.run(scenario())
    check("connect با packer دارای slots exception نداد", True)
    check("صف با proxy عوض شده، نه متد packer",
          isinstance(queue, _PrioritySendQueue), f"-> {type(queue)}")
    check("packer اصلی MessagePacker مانده",
          inner_name == "SlottedMessagePacker", f"-> {inner_name}")
    check("حذف همچنان جلوتر از send است",
          names == ["DeleteMessagesRequest", "SendMessageRequest"], f"-> {names}")
    check("متد append کلاس packer عوض نشده",
          SlottedMessagePacker.append is not queue.append)


def test_main_connect_path_does_not_raise():
    print("\n### مسیر startup شبیه main.py بعد از connect")

    async def scenario():
        logger = Logger()

        class Sender:
            def __init__(self):
                self._pending_state = {}
                self._send_queue = SlottedMessagePacker()

            async def _reconnect(self, last_error):
                return "ok"

        class StartupClient:
            def __init__(self):
                self._sender = None
                self.connected = False

            async def _call(self, sender, request, ordered=False,
                            flood_sleep_threshold=None):
                return "ok"

            async def delete_messages(self, *a, **k):
                return "deleted"

            async def edit_permissions(self, *a, **k):
                return "muted"

            async def kick_participant(self, *a, **k):
                return "banned"

            async def connect(self):
                self._sender = Sender()
                self.connected = True
                return True

        client = StartupClient()
        install(client, logger)
        await client.connect()
        await client.delete_messages(-1, [1])
        return client.connected, isinstance(
            client._sender._send_queue, _PrioritySendQueue
        )

    connected, proxied = asyncio.run(scenario())
    check("connect موفق شد", connected is True)
    check("بعد از connect proxy نصب است", proxied is True)


def main():
    test_classify_and_unwrap()
    test_permanent_matcher()
    test_get_users_404_not_resent()
    test_reconnect_does_not_requeue_404()
    test_slow_send_does_not_block_delete()
    test_second_send_waits_first_but_delete_does_not()
    test_delete_queue_skips_404_retry()
    test_delete_queue_still_retries_timeout()
    test_packer_puts_delete_first()
    test_install_idempotent()
    test_slotted_packer_is_not_mutated()
    test_main_connect_path_does_not_raise()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
