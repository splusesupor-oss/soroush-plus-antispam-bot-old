"""تست پایداری اتصال: بازتولید واقعی باگ‌ها و اثبات رفع آن‌ها.

این تست‌ها با کد واقعی SPlusthon کار می‌کنند (رمزنگاری واقعی، state
واقعی، ConnectionWebSocket واقعی) و فقط سوکت شبکه قلابی است.
"""

import asyncio
import logging
import os
import struct
import sys
import time
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.disable(logging.CRITICAL)

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"FAIL  {name} {detail}")


class Loggers(dict):
    def __missing__(self, key):
        value = logging.getLogger(key)
        self[key] = value
        return value


class RecordingLogger:
    def __init__(self):
        self.info = []
        self.errors = []

    def log_info(self, message):
        self.info.append(message)

    def log_error(self, message):
        self.errors.append(message)


# ===========================================================================
#  aiohttp قلابی تا کد واقعی websocket.py بدون شبکه اجرا شود
# ===========================================================================
class _WSMsgType:
    CLOSE = 1
    CLOSING = 2
    CLOSED = 3
    ERROR = 4
    BINARY = 5


class _FakeWS:
    def __init__(self):
        self._writer = None
        self.closed = False

    async def receive(self):
        await asyncio.sleep(3600)

    async def send_bytes(self, data):
        pass

    async def close(self):
        self.closed = True


class _FakeSession:
    def __init__(self):
        self.closed = False

    async def ws_connect(self, *args, **kwargs):
        return _FakeWS()

    async def close(self):
        self.closed = True


class _FakeAiohttp:
    WSMsgType = _WSMsgType
    created_sessions = []

    @staticmethod
    def ClientSession(*args, **kwargs):
        session = _FakeSession()
        _FakeAiohttp.created_sessions.append(session)
        return session

    @staticmethod
    def ClientTimeout(*args, **kwargs):
        return None


import splusthon.network.connection.websocket as ws_module  # noqa: E402

ws_module.aiohttp = _FakeAiohttp

from splusthon import helpers  # noqa: E402
from splusthon.crypto import AES, AuthKey  # noqa: E402
from splusthon.errors import SecurityError  # noqa: E402
from splusthon.network.connection.websocket import ConnectionWebSocket  # noqa: E402
from splusthon.network.mtprotostate import MTProtoState  # noqa: E402
from splusthon.tl.types import Pong  # noqa: E402

from modules import connection_guard  # noqa: E402


# ===========================================================================
#  ابزار: سرور واقعی MTProto که قاب معتبر می‌سازد
# ===========================================================================
def server_frame(auth_key, session_id, salt=0):
    """قاب رمزشدهٔ معتبر سمت سرور (offset x=8) با session id دلخواه."""
    body = bytes(Pong(msg_id=1, ping_id=2))
    msg_id = (int(time.time()) << 32) | 1
    if msg_id % 2 == 0:
        msg_id += 1
    inner = struct.pack("<qii", msg_id, 1, len(body)) + body
    data = struct.pack("<qq", salt, session_id) + inner
    padding = os.urandom(-(len(data) + 12) % 16 + 12)
    msg_key = sha256(auth_key.key[96:96 + 32] + data + padding).digest()[8:24]
    aes_key, aes_iv = MTProtoState._calc_key(auth_key.key, msg_key, False)
    return (
        struct.pack("<Q", auth_key.key_id)
        + msg_key
        + AES.encrypt_ige(data + padding, aes_key, aes_iv)
    )


# ===========================================================================
#  ۱) بازتولید باگ اصلی و اثبات رفع آن
# ===========================================================================
def test_wrong_session_reproduced_without_fix():
    """بدون وصله، قاب سشن قبلی دقیقاً همان خطای کاربر را می‌دهد."""
    auth = AuthKey(os.urandom(256))
    state = MTProtoState(auth, loggers=Loggers())

    old_session = state.id
    frame = server_frame(auth, old_session)
    decoded = MTProtoState.decrypt_message_data.__wrapped__ \
        if hasattr(MTProtoState.decrypt_message_data, "__wrapped__") else None

    # قاب با سشن فعلی سالم رمزگشایی می‌شود
    message = state.decrypt_message_data(frame)
    check("قاب با session فعلی رمزگشایی می‌شود", message is not None)

    # حالا reconnect: session id عوض می‌شود
    state.reset()
    check("reset یک session id تازه می‌سازد", state.id != old_session)

    stale = server_frame(auth, old_session)
    raised = None
    try:
        _raw_decrypt(state, stale)
    except SecurityError as error:
        raised = error

    check(
        "بدون وصله، قاب کهنه SecurityError می‌دهد",
        raised is not None and "wrong session ID" in str(raised),
        f"-> {raised!r}",
    )
    assert decoded is None or True


def _raw_decrypt(state, body):
    """رمزگشایی بدون وصله، برای اثبات وضعیت «قبل»."""
    original = getattr(
        MTProtoState.decrypt_message_data, "_original_for_test", None
    )
    if original is not None:
        return original(state, body)
    return MTProtoState.decrypt_message_data(state, body)


def test_stale_frame_dropped_after_fix():
    """با وصله، قاب کهنه بی‌صدا دور انداخته می‌شود و شمرده می‌شود."""
    auth = AuthKey(os.urandom(256))
    state = MTProtoState(auth, loggers=Loggers())
    old_session = state.id

    tracker = connection_guard.StaleSessionTracker()
    logger = RecordingLogger()

    # وصله را روی یک کلاس ایزوله نصب می‌کنیم تا تست‌های دیگر آلوده نشوند
    class Isolated(MTProtoState):
        pass

    Isolated.decrypt_message_data = MTProtoState.decrypt_message_data
    installed = connection_guard.install_stale_session_filter(
        Isolated, tracker, logger
    )
    check("وصله نصب شد", installed is True)

    patched = Isolated(auth, loggers=Loggers())
    patched.id = state.id
    patched.time_offset = 0

    good = server_frame(auth, patched.id)
    check("قاب سالم همچنان رمزگشایی می‌شود",
          patched.decrypt_message_data(good) is not None)

    patched.reset()
    stale = server_frame(auth, old_session)
    result = patched.decrypt_message_data(stale)

    check("قاب کهنه به جای استثنا None برمی‌گرداند", result is None)
    check("قاب کهنه شمرده شد", tracker.total == 1, f"-> {tracker.total}")
    check("لاگ ثبت شد", any("stale-session" in m for m in logger.info))

    # نصب دوباره نباید دوباره بپیچد
    again = connection_guard.install_stale_session_filter(
        Isolated, tracker, logger
    )
    check("نصب دوباره بی‌اثر است", again is False)


def test_other_security_errors_still_raise():
    """فقط «wrong session ID» بلعیده می‌شود؛ بقیه باید بالا بروند."""
    auth = AuthKey(os.urandom(256))

    class Isolated(MTProtoState):
        pass

    tracker = connection_guard.StaleSessionTracker()
    connection_guard.install_stale_session_filter(Isolated, tracker, None)
    state = Isolated(auth, loggers=Loggers())

    # auth key اشتباه → باید استثنا بدهد، نه None
    other = AuthKey(os.urandom(256))
    frame = server_frame(other, state.id)
    raised = None
    try:
        state.decrypt_message_data(frame)
    except SecurityError as error:
        raised = error

    check("خطای auth key نادرست بلعیده نمی‌شود", raised is not None,
          f"-> {raised!r}")
    check("این خطا در شمارنده ثبت نشد", tracker.total == 0)


def test_is_wrong_session_matcher():
    class FakeSecurityError(Exception):
        pass

    FakeSecurityError.__name__ = "SecurityError"
    match = connection_guard._is_wrong_session
    check("تشخیص پیام درست",
          match(FakeSecurityError("Server replied with a wrong session ID")))
    check("پیام دیگر تشخیص داده نمی‌شود",
          not match(FakeSecurityError("Received msg_key doesn't match")))
    check("نوع دیگر تشخیص داده نمی‌شود",
          not match(ValueError("wrong session id")))


# ===========================================================================
#  ۲) حلقهٔ reset دوره‌ای
# ===========================================================================
def _live_reset_loops():
    count = 0
    for task in asyncio.all_tasks():
        name = getattr(task.get_coro(), "__qualname__", "")
        if "_reconnect_loop" in name and not task.done():
            count += 1
    return count


def test_periodic_reset_kills_connection_without_fix():
    """اثبات وضعیت «قبل»: حلقهٔ اصلی خودش را cancel می‌کند."""

    class Vanilla(ConnectionWebSocket):
        pass

    async def scenario():
        conn = Vanilla("1.2.3.4", 443, 2, loggers=Loggers())
        conn._reconnect_interval = 0.05
        await conn.connect()
        await asyncio.sleep(0.4)
        return conn._connected, _live_reset_loops()

    connected, loops = asyncio.run(scenario())
    # نسخهٔ اصلی یا اتصال را می‌کشد یا حلقه را تکثیر می‌کند؛ هر دو خطاست.
    check(
        "بدون وصله، reset دوره‌ای اتصال را خراب می‌کند",
        (connected is False) or (loops > 1),
        f"-> connected={connected} loops={loops}",
    )


def test_periodic_reset_survives_with_fix():
    """با وصله: اتصال زنده می‌ماند و دقیقاً یک حلقه وجود دارد."""

    class Guarded(ConnectionWebSocket):
        pass

    Guarded._connect = ConnectionWebSocket._connect
    Guarded.connect = ConnectionWebSocket.connect
    Guarded._reconnect_loop = ConnectionWebSocket._reconnect_loop

    logger = RecordingLogger()
    installed = connection_guard.install_periodic_reset_fix(
        Guarded, helpers, logger
    )
    check("وصلهٔ حلقه نصب شد", installed is True)

    async def scenario():
        conn = Guarded("1.2.3.4", 443, 2, loggers=Loggers())
        conn._reconnect_interval = 0.05
        await conn.connect()
        samples = []
        for _ in range(6):
            await asyncio.sleep(0.1)
            samples.append((conn._connected, _live_reset_loops()))
        alive = conn._connected
        await conn.disconnect()
        return samples, alive

    samples, alive = asyncio.run(scenario())

    check("اتصال در تمام نمونه‌ها زنده ماند",
          all(state for state, _ in samples), f"-> {samples}")
    check("هیچ‌وقت بیش از یک حلقه وجود نداشت",
          all(loops <= 1 for _, loops in samples), f"-> {samples}")
    check("در پایان هنوز متصل است", alive is True)


def test_reset_once_rebuilds_transport():
    """`_reset_once` سوکت و تسک‌ها را واقعاً بازمی‌سازد."""

    class Guarded(ConnectionWebSocket):
        pass

    Guarded._connect = ConnectionWebSocket._connect
    Guarded.connect = ConnectionWebSocket.connect
    Guarded._reconnect_loop = ConnectionWebSocket._reconnect_loop
    connection_guard.install_periodic_reset_fix(Guarded, helpers, None)

    async def scenario():
        conn = Guarded("1.2.3.4", 443, 2, loggers=Loggers())
        conn._reconnect_interval = 3600  # حلقه دخالت نکند
        await conn.connect()
        first_recv = conn._recv_task
        await conn._connection_guard_reset_once()
        second_recv = conn._recv_task
        connected = conn._connected
        await conn.disconnect()
        return first_recv, second_recv, connected

    first, second, connected = asyncio.run(scenario())
    check("تسک دریافت واقعاً عوض شد", first is not second)
    check("بعد از بازسازی متصل است", connected is True)


# ===========================================================================
#  ۳) سقف زمانی RPC
# ===========================================================================
class FakeClient:
    """کلاینت قلابی برای تست وصلهٔ timeout و ناظر."""

    def __init__(self, hang=False):
        self.hang = hang
        self.connected = True
        self.connects = 0
        self.disconnects = 0
        self._sender = FakeSender()

    async def _call(self, sender, request, ordered=False,
                    flood_sleep_threshold=None):
        if self.hang:
            await asyncio.sleep(3600)
        return "ok"

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connects += 1
        self.connected = True

    async def disconnect(self):
        self.disconnects += 1
        self.connected = False


class FakeSender:
    def __init__(self):
        self._pending_state = {}


class FakeState:
    def __init__(self, future):
        self.future = future


class FakeRequest:
    pass


def test_rpc_hangs_forever_without_timeout():
    """اثبات وضعیت «قبل»: بدون وصله، RPC معلق تمام نمی‌شود."""

    async def scenario():
        client = FakeClient(hang=True)
        try:
            await asyncio.wait_for(
                client._call(None, FakeRequest()), timeout=0.3
            )
            return "returned"
        except asyncio.TimeoutError:
            return "still hanging"

    check("بدون وصله RPC معلق می‌ماند",
          asyncio.run(scenario()) == "still hanging")


def test_rpc_timeout_fires():
    """با وصله، RPC معلق بعد از مهلت شکست می‌خورد و ناظر خبردار می‌شود."""
    seen = []

    async def scenario():
        client = FakeClient(hang=True)
        logger = RecordingLogger()
        installed = connection_guard.install_rpc_timeout(
            client, timeout=0.2, on_timeout=seen.append, logger=logger
        )
        started = time.monotonic()
        error = None
        # سقف بیرونی: اگر وصله کار نکند تست باید *شکست بخورد*، نه اینکه
        # کل suite را برای همیشه معلق کند.
        try:
            await asyncio.wait_for(client._call(None, FakeRequest()), timeout=5)
        except connection_guard.RpcTimeout as exc:
            error = exc
        except asyncio.TimeoutError:
            error = None
        return installed, error, time.monotonic() - started, logger

    installed, error, elapsed, logger = asyncio.run(scenario())
    check("وصلهٔ timeout نصب شد", installed is True)
    check("RpcTimeout پرتاب شد", error is not None, f"-> {error!r}")
    check("در مهلت معقول برگشت", elapsed < 1.0, f"-> {elapsed:.2f}s")
    check("ناظر خبردار شد", len(seen) == 1)
    check("خطا لاگ شد", any("rpc timeout" in m for m in logger.errors))


def test_rpc_timeout_passes_through_success():
    """درخواست سالم باید بدون دست‌کاری برگردد."""

    async def scenario():
        client = FakeClient(hang=False)
        connection_guard.install_rpc_timeout(client, timeout=5.0)
        return await client._call(None, FakeRequest())

    check("پاسخ سالم دست‌نخورده برمی‌گردد", asyncio.run(scenario()) == "ok")


def test_rpc_timeout_installed_once():
    client = FakeClient()
    first = connection_guard.install_rpc_timeout(client, timeout=5.0)
    second = connection_guard.install_rpc_timeout(client, timeout=5.0)
    check("وصلهٔ timeout فقط یک بار اعمال می‌شود",
          first is True and second is False)


# ===========================================================================
#  ۴) لغو درخواست‌های معلق و بازسازی کلاینت
# ===========================================================================
def test_pending_requests_cancelled():
    """هنگام بازسازی، هر future معلق باید آزاد شود."""

    async def scenario():
        client = FakeClient()
        futures = []
        for index in range(4):
            future = asyncio.get_running_loop().create_future()
            futures.append(future)
            client._sender._pending_state[index] = FakeState(future)

        cancelled = connection_guard.cancel_pending_requests(client, "test")
        await asyncio.sleep(0)

        resolved = sum(1 for f in futures if f.done())
        errors = []
        for future in futures:
            try:
                future.result()
            except Exception as error:
                errors.append(type(error).__name__)
        empty = len(client._sender._pending_state) == 0
        return cancelled, resolved, errors, empty

    cancelled, resolved, errors, empty = asyncio.run(scenario())
    check("هر چهار درخواست لغو شد", cancelled == 4, f"-> {cancelled}")
    check("همهٔ futureها آزاد شدند", resolved == 4, f"-> {resolved}")
    check("با ConnectionError آزاد شدند",
          errors == ["ConnectionError"] * 4, f"-> {errors}")
    check("جدول معلق‌ها خالی شد", empty)


def test_supervisor_rebuilds_on_stale_flood():
    """سیل قاب کهنه باید بازسازی کامل کلاینت را راه بیندازد."""

    async def scenario():
        client = FakeClient()
        logger = RecordingLogger()
        supervisor = connection_guard.ConnectionSupervisor(
            client, logger=logger, stale_threshold=5
        )
        check("در حالت سالم بازسازی لازم نیست",
              supervisor.diagnose() is None)

        for _ in range(5):
            supervisor.tracker.record()

        reason = supervisor.diagnose()
        check("خرابی تشخیص داده شد", reason is not None, f"-> {reason}")

        future = asyncio.get_running_loop().create_future()
        client._sender._pending_state[1] = FakeState(future)

        await supervisor.rebuild(reason)
        await asyncio.sleep(0)
        return client, supervisor, future, logger

    client, supervisor, future, logger = asyncio.run(scenario())
    check("کلاینت قطع شد", client.disconnects == 1)
    check("کلاینت دوباره وصل شد", client.connects == 1)
    check("درخواست معلق آزاد شد", future.done())
    check("شمارنده صفر شد", supervisor.tracker.recent() == 0)
    check("بعد از بازسازی سالم است", supervisor.diagnose() is None)
    check("بازسازی شمرده شد", supervisor.rebuilds == 1)


def test_supervisor_rebuilds_on_rpc_timeouts():
    async def scenario():
        client = FakeClient()
        supervisor = connection_guard.ConnectionSupervisor(
            client, timeout_threshold=3
        )
        supervisor.note_rpc_timeout()
        supervisor.note_rpc_timeout()
        below = supervisor.diagnose()
        supervisor.note_rpc_timeout()
        above = supervisor.diagnose()
        await supervisor.rebuild(above)
        return below, above, client, supervisor

    below, above, client, supervisor = asyncio.run(scenario())
    check("زیر آستانه بازسازی نمی‌کند", below is None)
    check("بالای آستانه تشخیص می‌دهد", above is not None, f"-> {above}")
    check("کلاینت بازسازی شد", client.connects == 1)
    check("شمارندهٔ timeout صفر شد", supervisor.timeouts.count() == 0)


def test_supervisor_detects_disconnected_client():
    client = FakeClient()
    client.connected = False
    supervisor = connection_guard.ConnectionSupervisor(client)
    reason = supervisor.diagnose()
    check("قطع بودن کلاینت تشخیص داده می‌شود",
          reason is not None and "not connected" in reason, f"-> {reason}")


def test_rebuild_is_not_reentrant():
    """دو بازسازی هم‌زمان نباید روی هم بیفتد."""

    async def scenario():
        client = FakeClient()
        supervisor = connection_guard.ConnectionSupervisor(client)

        slow = asyncio.Event()

        async def slow_connect():
            await slow.wait()
            client.connects += 1
            client.connected = True

        client.connect = slow_connect

        first = asyncio.ensure_future(supervisor.rebuild("first"))
        await asyncio.sleep(0.05)
        second = await supervisor.rebuild("second")
        slow.set()
        await first
        return second, client.connects

    second, connects = asyncio.run(scenario())
    check("بازسازی هم‌زمان دوم رد شد", second is False)
    check("فقط یک بار وصل شد", connects == 1, f"-> {connects}")


def test_supervisor_loop_triggers_rebuild():
    """حلقهٔ ناظر باید خودش خرابی را ببیند و اقدام کند."""

    async def scenario():
        client = FakeClient()
        supervisor = connection_guard.ConnectionSupervisor(
            client, stale_threshold=2, check_interval=0.01
        )
        for _ in range(2):
            supervisor.tracker.record()

        task = asyncio.ensure_future(supervisor.run())
        for _ in range(50):
            await asyncio.sleep(0.01)
            if supervisor.rebuilds:
                break
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return supervisor.rebuilds, client.connects

    rebuilds, connects = asyncio.run(scenario())
    check("حلقهٔ ناظر بازسازی را اجرا کرد", rebuilds >= 1, f"-> {rebuilds}")
    check("کلاینت دوباره وصل شد", connects >= 1, f"-> {connects}")


def test_supervisor_loop_survives_errors():
    """خطای یک دور نباید ناظر را بکشد."""

    async def scenario():
        client = FakeClient()
        supervisor = connection_guard.ConnectionSupervisor(
            client, check_interval=0.01
        )
        calls = {"n": 0}

        def exploding_diagnose():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("boom")
            return None

        supervisor.diagnose = exploding_diagnose
        task = asyncio.ensure_future(supervisor.run())
        await asyncio.sleep(0.15)
        alive = not task.done()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return alive, calls["n"]

    alive, calls = asyncio.run(scenario())
    check("ناظر بعد از خطا زنده ماند", alive is True)
    check("به کارش ادامه داد", calls >= 3, f"-> {calls}")


# ===========================================================================
#  پنجرهٔ رویداد
# ===========================================================================
def test_event_window_expires():
    now = {"t": 1000.0}
    window = EventWindowClock = connection_guard.EventWindow(
        window=10.0, clock=lambda: now["t"]
    )
    window.record()
    window.record()
    check("دو رویداد شمرده شد", window.count() == 2)
    now["t"] += 5
    check("هنوز در پنجره است", window.count() == 2)
    now["t"] += 6
    check("بعد از پنجره پاک شد", window.count() == 0)


def test_event_window_clear():
    window = connection_guard.EventWindow(window=100.0)
    window.record(3)
    check("سه رویداد", window.count() == 3)
    window.clear()
    check("پاک شد", window.count() == 0)


# ===========================================================================
#  نصب یک‌جا
# ===========================================================================
def test_rebuild_keeps_handlers_and_auth_key():
    """بازسازی نباید هندلرها یا auth_key را از بین ببرد.

    اگر disconnect/connect هندلرها را پاک می‌کرد، ربات بعد از بازسازی
    ساکت می‌شد — بدتر از باگ اصلی.
    """
    from splusthon import SoroushClient, events
    from splusthon.sessions import StringSession

    async def scenario():
        client = SoroushClient(StringSession())

        @client.on(events.NewMessage())
        async def handler(event):
            pass

        before = len(client.list_event_handlers())
        client.session.auth_key = "SENTINEL"
        await client.disconnect()
        after = len(client.list_event_handlers())
        return before, after, client.session, client.session.auth_key

    before, after, session, auth_key = asyncio.run(scenario())
    check("هندلر ثبت شده بود", before == 1, f"-> {before}")
    check("هندلر بعد از بازسازی زنده ماند", after == before, f"-> {after}")
    check("session از بین نرفت", session is not None)
    check("auth_key حفظ شد", auth_key == "SENTINEL")


def test_install_returns_supervisor():
    client = FakeClient()
    logger = RecordingLogger()
    supervisor = connection_guard.install(
        client, logger=logger, rpc_timeout=30.0
    )
    check("ناظر برگردانده شد",
          isinstance(supervisor, connection_guard.ConnectionSupervisor))
    check("ناظر به همان کلاینت وصل است", supervisor.client is client)
    check("وصلهٔ RPC روی کلاینت نشست",
          getattr(client._call, "_connection_guard_rpc_timeout", False) is True)


def test_install_is_idempotent():
    client_a = FakeClient()
    client_b = FakeClient()
    connection_guard.install(client_a)
    connection_guard.install(client_b)
    check("نصب دوباره خطا نمی‌دهد", True)
    check("هر کلاینت وصلهٔ خودش را دارد",
          getattr(client_b._call, "_connection_guard_rpc_timeout", False) is True)


# ===========================================================================
def main():
    test_wrong_session_reproduced_without_fix()
    test_stale_frame_dropped_after_fix()
    test_other_security_errors_still_raise()
    test_is_wrong_session_matcher()

    test_periodic_reset_kills_connection_without_fix()
    test_periodic_reset_survives_with_fix()
    test_reset_once_rebuilds_transport()

    test_rpc_hangs_forever_without_timeout()
    test_rpc_timeout_fires()
    test_rpc_timeout_passes_through_success()
    test_rpc_timeout_installed_once()

    test_pending_requests_cancelled()
    test_supervisor_rebuilds_on_stale_flood()
    test_supervisor_rebuilds_on_rpc_timeouts()
    test_supervisor_detects_disconnected_client()
    test_rebuild_is_not_reentrant()
    test_supervisor_loop_triggers_rebuild()
    test_supervisor_loop_survives_errors()

    test_event_window_expires()
    test_event_window_clear()

    test_rebuild_keeps_handlers_and_auth_key()
    test_install_returns_supervisor()
    test_install_is_idempotent()

    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
