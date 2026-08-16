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
    URGENT,
    _HEAVY_TIMEOUT_S,
    _MAX_SENDER_PENDING,
    _PrioritySendQueue,
    cached_invalid_users,
    cancel_inflight_request,
    clear_invalid_user_cache,
    drop_invalid_pending,
    drop_reconnect_pending,
    drop_stale_low_pending,
    get_users_ids,
    install,
    is_permanent_rpc_error,
    mark_method_urgent,
    remember_invalid_users,
    request_priority,
    urgent_rpc,
    unwrap_request,
)
from modules.urgent_send import is_urgent_text, reply_urgent, urgent_send

HEAVY_NOTICE = "🗑 ۱۰ پیام هرزنامه پاک شد"

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


class GetMessagesRequest:
    def __init__(self, ids=None):
        self.ids = ids or []


class GetChannelDifferenceRequest:
    def __init__(self, channel=None):
        self.channel = channel


class PingRequest:
    def __init__(self, ping_id=1):
        self.ping_id = ping_id


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

    async def get(self):
        if not self._deque:
            self._ready.clear()
            await self._ready.wait()
        batch = []
        while self._deque:
            batch.append(self._deque.popleft())
        return batch, b"data"


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
        if name in {"GetMessagesRequest", "GetChannelDifferenceRequest"}:
            await asyncio.sleep(self.send_ms / 1000.0)
            return "history"
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
    check("send خالی اولویت پایین است", request_priority(inner) == "low")
    check("اعلان هرزنامه low می‌ماند",
          request_priority(SendMessageRequest(-1, HEAVY_NOTICE)) == "low")
    check("پاسخ سلام بدون context هم urgent است",
          request_priority(SendMessageRequest(-1, "سلام 👋")) == URGENT)
    check("delete اولویت بالا است",
          request_priority(DeleteMessagesRequest()) == "high")
    check("GetUsers عادی است", request_priority(GetUsersRequest([])) == "normal")
    check("GetMessages سنگین و gated است",
          request_priority(GetMessagesRequest([1])) == "low")
    check("GetChannelDifference سنگین است",
          request_priority(GetChannelDifferenceRequest(-1)) == "low")
    check("ping مثل urgent است", request_priority(PingRequest(1)) == URGENT)
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
            await client._call(client._sender, SendMessageRequest(-1, HEAVY_NOTICE))
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
            await client._call(client._sender, SendMessageRequest(-2, f"{HEAVY_NOTICE} {tag}"))
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
        send = RequestState(SendMessageRequest(-1, HEAVY_NOTICE))
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
        send = RequestState(SendMessageRequest(-1, HEAVY_NOTICE))
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


def test_urgent_reply_bypasses_gate():
    print("\n### پاسخ urgent پشت send سنگین نمی‌ماند")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient(send_ms=200)
        original = client._call

        async def mixed_call(sender, request, ordered=False, flood_sleep_threshold=None):
            if getattr(request, "message", None) == "سلام":
                name = type(outgoing_rpc.unwrap_request(request)).__name__
                client.calls.append(name)
                client.started.append((name, time.perf_counter()))
                await asyncio.sleep(0.01)
                return "sent"
            return await original(sender, request, ordered, flood_sleep_threshold)

        client._call = mixed_call
        install(client, logger)
        marks = {}

        async def heavy_send():
            marks["send_start"] = time.perf_counter()
            await client._call(client._sender, SendMessageRequest(-3, HEAVY_NOTICE))
            marks["send_end"] = time.perf_counter()

        async def reply():
            await asyncio.sleep(0.03)
            marks["reply_start"] = time.perf_counter()
            with urgent_rpc():
                await client._call(client._sender, SendMessageRequest(-3, "سلام"))
            marks["reply_end"] = time.perf_counter()

        await asyncio.gather(heavy_send(), reply())
        return marks

    marks = asyncio.run(scenario())
    reply_ms = (marks["reply_end"] - marks["reply_start"]) * 1000
    during = marks["reply_end"] < marks["send_end"]
    print(f"    reply_ms={reply_ms:.1f}")
    check("reply قبل از پایان send سنگین تمام شد", during)
    check("reply پشت گیت ۱–۲ ثانیه نماند", reply_ms < 80, f"-> {reply_ms:.1f}ms")


def test_packer_urgent_before_delete():
    print("\n### packer: پاسخ urgent جلوتر از delete و send سنگین")
    clear_invalid_user_cache()

    async def scenario():
        client = FakeClient()
        install(client, Logger())
        packer = client._sender._send_queue
        heavy = RequestState(SendMessageRequest(-1, HEAVY_NOTICE))
        delete = RequestState(DeleteMessagesRequest([1]))
        packer.append(heavy)
        packer.append(delete)
        with urgent_rpc():
            reply = RequestState(SendMessageRequest(-1, "خوبی"))
            packer.append(reply)
        return [getattr(item.request, "message", type(item.request).__name__)
                for item in packer._deque]

    names = asyncio.run(scenario())
    check("اول پاسخ urgent است", names[0] == "خوبی", f"-> {names}")
    check("بعد delete است", names[1] == "DeleteMessagesRequest", f"-> {names}")
    check("send سنگین آخر است", names[-1] == HEAVY_NOTICE, f"-> {names}")


def test_send_response_excludes_reply():
    print("\n### SEND_RESPONSE زمان انتظار reply را حساب نمی‌کند")
    from modules.outgoing_profiler import (
        begin_response_measurement,
        end_response_measurement,
        instrument_event,
        response_rpc_ms,
    )

    class Event:
        def __init__(self, client):
            self.client = client
            self.chat_id = -4

        async def reply(self, text):
            with urgent_rpc():
                await asyncio.sleep(0.12)
                return "sent"

    async def scenario():
        logger = Logger()
        event = Event(FakeClient())
        instrument_event(event, logger)
        token = begin_response_measurement()
        await event.reply("سلام")
        waited = response_rpc_ms()
        end_response_measurement(token)
        return waited

    waited = asyncio.run(scenario())
    check("انتظار reply در SEND_RESPONSE نیست", waited < 20, f"-> {waited:.1f}ms")


def test_urgent_text_classifier():
    print("\n### متن پاسخ ساده urgent است، اعلان نیست")
    check("سلام 👋 urgent است", is_urgent_text("سلام 👋"))
    check("جانم ؟ 🦊 urgent است", is_urgent_text("جانم ؟ 🦊"))
    check("هعی urgent است", is_urgent_text("نکش دوست من 🦊🐥"))
    check("اعلان هرزنامه urgent نیست", not is_urgent_text(HEAVY_NOTICE))
    check("متن خالی urgent نیست", not is_urgent_text(""))
    check("متن بلند urgent نیست", not is_urgent_text("x" * 200))


def test_send_message_short_bypasses_gate_without_context():
    print("\n### send_message کوتاه بدون urgent_rpc از گیت رد می‌شود")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient(send_ms=200)
        original = client._call

        async def mixed_call(sender, request, ordered=False, flood_sleep_threshold=None):
            if getattr(request, "message", None) == "سلام 👋":
                name = type(outgoing_rpc.unwrap_request(request)).__name__
                client.calls.append(name)
                client.started.append((name, time.perf_counter()))
                await asyncio.sleep(0.01)
                return "sent"
            return await original(sender, request, ordered, flood_sleep_threshold)

        client._call = mixed_call
        install(client, logger)
        marks = {}

        async def heavy_send():
            marks["send_start"] = time.perf_counter()
            await client._call(client._sender, SendMessageRequest(-5, HEAVY_NOTICE))
            marks["send_end"] = time.perf_counter()

        async def reply():
            await asyncio.sleep(0.03)
            marks["reply_start"] = time.perf_counter()
            await client.send_message(-5, "سلام 👋")
            marks["reply_end"] = time.perf_counter()

        await asyncio.gather(heavy_send(), reply())
        return marks, logger

    marks, logger = asyncio.run(scenario())
    reply_ms = (marks["reply_end"] - marks["reply_start"]) * 1000
    during = marks["reply_end"] < marks["send_end"]
    print(f"    reply_ms={reply_ms:.1f}")
    check("سلام قبل از پایان notice تمام شد", during)
    check("سلام بدون context پشت گیت نماند", reply_ms < 80, f"-> {reply_ms:.1f}ms")
    check(
        "لاگ GATE برای سلام نیست",
        not any("OUTGOING RPC GATE" in line and "سلام" in line for line in logger.infos),
    )


def test_delete_after_urgent_stays_behind():
    print("\n### delete بعد از urgent نمی‌تواند جلوی آن بپرد")
    clear_invalid_user_cache()

    async def scenario():
        client = FakeClient()
        install(client, Logger())
        packer = client._sender._send_queue
        packer.append(RequestState(SendMessageRequest(-1, "سلام 👋")))
        packer.append(RequestState(DeleteMessagesRequest([1])))
        return [getattr(item.request, "message", type(item.request).__name__)
                for item in packer._deque]

    names = asyncio.run(scenario())
    check("اول سلام است", names[0] == "سلام 👋", f"-> {names}")
    check("delete بعد از سلام است", names[1] == "DeleteMessagesRequest", f"-> {names}")


def test_reconnect_drops_low_not_urgent():
    print("\n### reconnect اعلان LOW گیرکرده را دور می‌اندازد")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient()
        install(client, logger)
        low = RequestState(SendMessageRequest(-1, HEAVY_NOTICE))
        urgent = RequestState(SendMessageRequest(-1, "سلام 👋"))
        client._sender._pending_state[1] = low
        client._sender._pending_state[2] = urgent
        dropped = drop_stale_low_pending(client._sender, logger)
        return dropped, list(client._sender._pending_state), low.future, urgent.future, logger

    dropped, leftover, low_future, urgent_future, logger = asyncio.run(scenario())
    check("هر دو pending غیرkeepalive حذف شدند", dropped == 2, f"-> {dropped}")
    check("pending بعد از reconnect خالی است", leftover == [], f"-> {leftover}")
    check("future اعلان با خطا بسته شد",
          low_future.done() and isinstance(low_future.exception(), ConnectionError))
    check("future سلام هم بسته شد تا replay نشود",
          urgent_future.done() and isinstance(urgent_future.exception(), ConnectionError))
    check("لاگ reconnect ثبت شد",
          any("reason=reconnect" in line for line in logger.infos))


def test_greeting_during_spam_under_one_second():
    print("\n### سلام در گروه دیگر هنگام ban/delete زیر ۱ ثانیه")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient(send_ms=400)
        original = client._call

        async def mixed_call(sender, request, ordered=False, flood_sleep_threshold=None):
            text = getattr(request, "message", None)
            if text in {"سلام 👋", "ممنون، خوبم 😊", "جانم ؟ 🦊"}:
                client.calls.append(type(request).__name__)
                await asyncio.sleep(0.01)
                return "sent"
            return await original(sender, request, ordered, flood_sleep_threshold)

        client._call = mixed_call
        install(client, logger)
        times = {}

        async def spam_group():
            await client._call(client._sender, SendMessageRequest(-10, HEAVY_NOTICE))
            await client.delete_messages(-10, [1, 2, 3])

        async def greet(chat_id, text, tag):
            await asyncio.sleep(0.02)
            started = time.perf_counter()
            await urgent_send(client, chat_id, text)
            times[tag] = (time.perf_counter() - started) * 1000

        await asyncio.gather(
            spam_group(),
            greet(-20, "سلام 👋", "سلام"),
            greet(-21, "ممنون، خوبم 😊", "خوبی"),
            greet(-22, "جانم ؟ 🦊", "ربات"),
        )
        return times

    times = asyncio.run(scenario())
    for tag, elapsed in times.items():
        print(f"    {tag}={elapsed:.1f}ms")
        check(f"{tag} زیر ۱ ثانیه پاسخ داد", elapsed < 1000, f"-> {elapsed:.1f}ms")
        check(f"{tag} پشت cleanup نماند", elapsed < 80, f"-> {elapsed:.1f}ms")


def test_urgent_cuts_ahead_of_full_sender():
    print("\n### پاسخ کوتاه پشت sender_pending=152 نمی‌ماند")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient()
        install(client, logger)
        packer = client._sender._send_queue
        for index in range(40):
            packer.append(RequestState(DeleteMessagesRequest([index])))
        for index in range(_MAX_SENDER_PENDING + 10):
            client._sender._pending_state[index] = object()
        packer.append(RequestState(SendMessageRequest(-1, "نکش دوست من 🦊🐥")))
        started = time.perf_counter()
        batch, _data = await asyncio.wait_for(packer.get(), 1)
        elapsed_ms = (time.perf_counter() - started) * 1000
        names = [getattr(item.request, "message", type(item.request).__name__)
                 for item in batch]
        leftover = [getattr(item.request, "message", type(item.request).__name__)
                    for item in packer._deque]
        return names, leftover, elapsed_ms, packer._pending_count(), logger

    names, leftover, elapsed_ms, pending, logger = asyncio.run(scenario())
    print(f"    batch={names} leftover={len(leftover)} pending={pending} ms={elapsed_ms:.1f}")
    route = [line for line in logger.infos if line.startswith("SENDER ROUTE ")]
    check("فقط پاسخ هعی از packer خارج شد", names == ["نکش دوست من 🦊🐥"], f"-> {names}")
    check("deleteها در صف ماندند", leftover.count("DeleteMessagesRequest") == 40,
          f"-> {leftover[:3]}... n={len(leftover)}")
    check("منتظر خالی شدن pending نماند", elapsed_ms < 80, f"-> {elapsed_ms:.1f}ms")
    check("لاگ SENDER ROUTE ثبت شد", bool(route), f"-> {logger.infos}")
    check("لاگ urgent=True و cut_ahead=True دارد",
          any("type=reply" in line and "urgent=True" in line and "cut_ahead=True" in line
              for line in route),
          f"-> {route}")


def test_non_urgent_waits_when_pending_full():
    print("\n### اعلان پشت سقف pending می‌ماند، reply نمی‌ماند")
    clear_invalid_user_cache()

    async def scenario():
        client = FakeClient()
        install(client, Logger())
        packer = client._sender._send_queue
        packer.append(RequestState(SendMessageRequest(-1, HEAVY_NOTICE)))
        for index in range(_MAX_SENDER_PENDING + 4):
            client._sender._pending_state[index] = object()
        marks = {}

        async def wait_notice():
            marks["start"] = time.perf_counter()
            batch, _data = await packer.get()
            marks["end"] = time.perf_counter()
            return [getattr(item.request, "message", type(item.request).__name__)
                    for item in batch]

        async def later_reply():
            await asyncio.sleep(0.03)
            marks["reply_at"] = time.perf_counter()
            packer.append(RequestState(SendMessageRequest(-2, "سلام 👋")))

        notice_task = asyncio.create_task(wait_notice())
        await asyncio.gather(notice_task, later_reply())
        names = notice_task.result()
        return names, marks

    names, marks = asyncio.run(scenario())
    reply_first = marks["end"] >= marks["reply_at"]
    check("get بعد از ورود سلام برگشت", reply_first)
    check("اول سلام از packer آمد نه اعلان", names[0] == "سلام 👋", f"-> {names}")


def test_ping_cuts_ahead_of_delete():
    print("\n### ping جلوتر از delete می‌ایستد تا keepalive نمیرد")
    clear_invalid_user_cache()

    async def scenario():
        client = FakeClient()
        install(client, Logger())
        packer = client._sender._send_queue
        packer.append(RequestState(DeleteMessagesRequest([1])))
        packer.append(RequestState(PingRequest(9)))
        return [type(item.request).__name__ for item in packer._deque]

    names = asyncio.run(scenario())
    check("اول ping است", names[0] == "PingRequest", f"-> {names}")
    check("delete بعد از ping است", names[1] == "DeleteMessagesRequest", f"-> {names}")


def test_heavy_rpc_times_out_and_cancels():
    print("\n### GetMessages سنگین timeout و cancel می‌شود")
    clear_invalid_user_cache()
    import modules.outgoing_rpc as rpc

    async def scenario():
        logger = Logger()
        client = FakeClient(send_ms=400)
        install(client, logger)
        original_timeout = rpc._HEAVY_TIMEOUT_S
        rpc._HEAVY_TIMEOUT_S = 0.05
        started = time.perf_counter()
        error = None
        try:
            await client._call(client._sender, GetMessagesRequest([1, 2, 3]))
        except TimeoutError as exc:
            error = exc
        finally:
            rpc._HEAVY_TIMEOUT_S = original_timeout
        elapsed_ms = (time.perf_counter() - started) * 1000
        return error, elapsed_ms, logger

    error, elapsed_ms, logger = asyncio.run(scenario())
    print(f"    elapsed_ms={elapsed_ms:.1f}")
    check("TimeoutError آمد", isinstance(error, TimeoutError), f"-> {error!r}")
    check("زودتر از sleep سنگین برگشت", elapsed_ms < 250, f"-> {elapsed_ms:.1f}ms")
    check("لاگ HEAVY RPC CANCEL هست",
          any("HEAVY RPC CANCEL" in line for line in logger.infos),
          f"-> {logger.infos}")


def test_heavy_cancel_frees_pending_and_packer():
    print("\n### cancel باید pending و packer را خالی کند نه فقط coroutine")
    clear_invalid_user_cache()
    import modules.outgoing_rpc as rpc

    async def scenario():
        logger = Logger()
        client = FakeClient()

        async def parked_call(sender, request, ordered=False, flood_sleep_threshold=None):
            wrapped = InvokeWithoutUpdatesRequest(request)
            state = RequestState(wrapped)
            sender._pending_state[77] = state
            sender._send_queue.append(state)
            return await state.future

        client._call = parked_call
        install(client, logger)
        original_timeout = rpc._HEAVY_TIMEOUT_S
        rpc._HEAVY_TIMEOUT_S = 0.05
        error = None
        try:
            await client._call(client._sender, GetMessagesRequest([4, 5]))
        except TimeoutError as exc:
            error = exc
        finally:
            rpc._HEAVY_TIMEOUT_S = original_timeout
        pending = list(client._sender._pending_state)
        leftover = [
            type(outgoing_rpc.unwrap_request(item.request)).__name__
            for item in client._sender._send_queue._deque
        ]
        packer = client._sender._send_queue
        packer.append(RequestState(PingRequest(1)))
        started = time.perf_counter()
        batch, _data = await asyncio.wait_for(packer.get(), 1)
        ping_ms = (time.perf_counter() - started) * 1000
        ping_names = [type(item.request).__name__ for item in batch]
        dropped_line = next(
            (line for line in logger.infos if "HEAVY RPC CANCEL" in line), ""
        )
        return error, pending, leftover, ping_names, ping_ms, dropped_line

    error, pending, leftover, ping_names, ping_ms, dropped_line = asyncio.run(scenario())
    print(f"    pending={pending} leftover={leftover} ping_ms={ping_ms:.1f} log={dropped_line}")
    check("TimeoutError آمد", isinstance(error, TimeoutError), f"-> {error!r}")
    check("pending_rpc بعد از cancel خالی است", pending == [], f"-> {pending}")
    check("packer دیگر GetMessages ندارد", "GetMessagesRequest" not in leftover,
          f"-> {leftover}")
    check("لاگ dropped و sender_pending=0 دارد",
          "dropped=" in dropped_line and "sender_pending=0" in dropped_line,
          f"-> {dropped_line}")
    check("ping فوری از packer آمد", ping_names == ["PingRequest"], f"-> {ping_names}")
    check("ping زیر ۱ ثانیه منتظر نماند", ping_ms < 1000, f"-> {ping_ms:.1f}ms")


def test_reconnect_drops_heavy_not_ping():
    print("\n### reconnect تاریخچه سنگین را replay نمی‌کند")
    clear_invalid_user_cache()

    async def scenario():
        logger = Logger()
        client = FakeClient()
        install(client, logger)
        heavy = RequestState(GetChannelDifferenceRequest(-8))
        ping = RequestState(PingRequest(3))
        client._sender._pending_state[1] = heavy
        client._sender._pending_state[2] = ping
        dropped = drop_reconnect_pending(client._sender, logger)
        leftover = [
            type(state.request).__name__
            for state in client._sender._pending_state.values()
        ]
        return dropped, leftover, heavy.future, ping.future

    dropped, leftover, heavy_future, ping_future = asyncio.run(scenario())
    check("سنگین حذف شد", dropped == 1, f"-> {dropped}")
    check("ping ماند", leftover == ["PingRequest"], f"-> {leftover}")
    check("future سنگین بسته شد",
          heavy_future.done() and isinstance(heavy_future.exception(), ConnectionError))
    check("future ping باز ماند", not ping_future.done())


def test_reply_urgent_sets_lane():
    print("\n### reply_urgent مسیر event.reply را urgent می‌کند")

    class Event:
        def __init__(self):
            self.seen = None

        async def reply(self, text):
            self.seen = outgoing_rpc.current_priority()
            return text

    async def scenario():
        event = Event()
        result = await reply_urgent(event, "سلام 👋")
        return result, event.seen

    result, seen = asyncio.run(scenario())
    check("متن برگردانده شد", result == "سلام 👋")
    check("داخل reply اولویت urgent بود", seen == URGENT, f"-> {seen}")


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
    test_urgent_reply_bypasses_gate()
    test_packer_urgent_before_delete()
    test_send_response_excludes_reply()
    test_urgent_text_classifier()
    test_send_message_short_bypasses_gate_without_context()
    test_delete_after_urgent_stays_behind()
    test_reconnect_drops_low_not_urgent()
    test_greeting_during_spam_under_one_second()
    test_urgent_cuts_ahead_of_full_sender()
    test_non_urgent_waits_when_pending_full()
    test_ping_cuts_ahead_of_delete()
    test_heavy_rpc_times_out_and_cancels()
    test_heavy_cancel_frees_pending_and_packer()
    test_reconnect_drops_heavy_not_ping()
    test_reply_urgent_sets_lane()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
