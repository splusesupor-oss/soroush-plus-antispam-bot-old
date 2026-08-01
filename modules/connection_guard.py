"""لایهٔ پایداری اتصال روی SPlusthon.

این ماژول چهار نقص اثبات‌شده در لایهٔ شبکهٔ SPlusthon را برطرف می‌کند.
هیچ‌کدام «try/except موقت» نیست؛ هر مورد ریشهٔ باگ را می‌بندد.

------------------------------------------------------------------
۱) قاب‌های کهنهٔ سشن قبلی  →  «Server replied with a wrong session ID»
------------------------------------------------------------------
`MTProtoSender._reconnect()` هنگام اتصال دوباره `self._state.reset()`
را صدا می‌زند که یک session id تازه می‌سازد. اما قاب‌هایی که پیش از
reset از سرور رسیده و هنوز در `connection._recv_queue` مانده‌اند با
session id *قدیمی* امضا شده‌اند. `decrypt_message_data()` آن‌ها را با
session id جدید مقایسه می‌کند و `SecurityError` می‌اندازد.

این قاب‌ها از نظر امنیتی معتبرند (auth_key و msg_key هر دو تأیید
شده‌اند)؛ فقط متعلق به سشن قبلی‌اند. راه‌حل درست دور انداختن بی‌صدای
آن‌هاست، نه بالا بردن استثنا. اگر این حالت ادامه‌دار شد یعنی سشن
واقعاً خراب است و ناظر، کلاینت را بازسازی می‌کند.

------------------------------------------------------------------
۲) حلقهٔ reset دوره‌ای خودش را cancel می‌کند
------------------------------------------------------------------
`ConnectionWebSocket._reconnect_loop()` هر ۱۸۰۰ ثانیه `self.disconnect()`
را صدا می‌زند، و `disconnect()` با `helpers._cancel(...,
reconnect_task=self._reconnect_task)` **همان تسکی را که در حال اجراست**
cancel می‌کند. اجرای واقعی نشان داد:

  * حلقه در نقطهٔ `disconnect()` می‌میرد و به `_connect()` نمی‌رسد،
  * یا `_connect()` حلقهٔ دومی می‌سازد و تعداد حلقه‌ها بالا می‌رود،
  * و ترنسپورت می‌تواند با `_connected=False` برای همیشه مرده بماند.

`_recv()` آن‌گاه `ConnectionError` می‌دهد → سِندر `_reconnect` می‌کند →
`_state.reset()` → قاب‌های کهنه → خطای بند ۱. همین زنجیره است که بعد
از چند ساعت ربات را زمین می‌زند.

------------------------------------------------------------------
۳) هیچ سقف زمانی روی RPC نیست
------------------------------------------------------------------
`UserMethods._call` هیچ `wait_for` ندارد. اگر پاسخ یک درخواست گم شود،
`await future` تا ابد معلق می‌ماند — همان «send_message چند دقیقه معطل
می‌شود» که کاربر گزارش کرده.

------------------------------------------------------------------
۴) هیچ مسیری برای بازسازی کامل کلاینت بدون ری‌استارت نیست
------------------------------------------------------------------
`ConnectionSupervisor` سلامت اتصال را می‌پاید و در صورت خرابی پایدار،
درخواست‌های معلق را لغو و کل کلاینت را دوباره connect می‌کند.
"""

import asyncio
import time


# ==========================================================================
#  ابزار کوچک: شمارندهٔ رویداد در پنجرهٔ زمانی
# ==========================================================================
class EventWindow:
    """تعداد رویدادها را در یک پنجرهٔ زمانی لغزان می‌شمارد."""

    def __init__(self, window=120.0, clock=time.monotonic):
        self.window = float(window)
        self._clock = clock
        self._events = []

    def record(self, count=1):
        now = self._clock()
        for _ in range(count):
            self._events.append(now)
        self._trim(now)
        return len(self._events)

    def count(self):
        self._trim(self._clock())
        return len(self._events)

    def clear(self):
        self._events.clear()

    def _trim(self, now):
        cutoff = now - self.window
        events = self._events
        while events and events[0] < cutoff:
            events.pop(0)


# ==========================================================================
#  ۱) دور انداختن قاب‌های کهنهٔ سشن قبلی
# ==========================================================================
_STALE_MARKER = "_connection_guard_stale_session"


class StaleSessionTracker:
    """قاب‌های متعلق به سشن قبلی را می‌شمارد."""

    def __init__(self, window=120.0):
        self.window = EventWindow(window)
        self.total = 0
        self.last_at = None

    def record(self):
        self.total += 1
        self.last_at = time.monotonic()
        return self.window.record()

    def recent(self):
        return self.window.count()

    def reset(self):
        self.window.clear()


def install_stale_session_filter(state_class, tracker, logger=None):
    """`decrypt_message_data` را طوری می‌پیچد که قاب سشن قبلی را دور بیندازد.

    قاب کهنه با `None` برگردانده می‌شود؛ دقیقاً همان چیزی که حلقهٔ
    دریافت برای «این پیام را نادیده بگیر» انتظار دارد. هر استثنای
    امنیتی دیگری دست‌نخورده بالا می‌رود.
    """
    original = getattr(state_class, "decrypt_message_data", None)
    if original is None or getattr(original, _STALE_MARKER, False):
        return False

    def decrypt_message_data(self, body):
        try:
            return original(self, body)
        except Exception as error:
            if not _is_wrong_session(error):
                raise
            recent = tracker.record()
            if logger is not None:
                logger.log_info(
                    "CONNECTION GUARD dropped stale-session frame "
                    f"recent={recent} total={tracker.total}"
                )
            return None

    setattr(decrypt_message_data, _STALE_MARKER, True)
    state_class.decrypt_message_data = decrypt_message_data
    return True


def _is_wrong_session(error):
    """آیا این استثنا همان «wrong session ID» است؟"""
    if error.__class__.__name__ != "SecurityError":
        return False
    return "wrong session id" in str(error).lower()


# ==========================================================================
#  ۲) حلقهٔ reset دوره‌ای که خودکشی نمی‌کند
# ==========================================================================
_LOOP_MARKER = "_connection_guard_safe_loop"


def install_periodic_reset_fix(connection_class, helpers, logger=None):
    """`_reconnect_loop` و `_connect` را امن می‌کند.

    دو تغییر:

    * `_connect` دیگر خودش حلقهٔ دوره‌ای نمی‌سازد. مالکیت حلقه فقط
      دست `connect()` است، پس هرگز دو حلقه هم‌زمان وجود ندارد.
    * حلقه پیش از `disconnect()` ارجاع خودش را کنار می‌گذارد تا
      `helpers._cancel` نتواند تسکِ در حال اجرا را cancel کند، و بعد
      از ساخت دوبارهٔ سوکت، تسک‌های ارسال/دریافت را برمی‌گرداند.
    """
    original_connect = getattr(connection_class, "_connect", None)
    if original_connect is None or getattr(original_connect, _LOOP_MARKER, False):
        return False

    async def _connect(self, timeout=None, ssl=None):
        # مالکیت حلقه به connect()/حلقهٔ موجود واگذار می‌شود.
        self._connection_guard_inhibit_loop = True
        try:
            return await original_connect(self, timeout=timeout, ssl=ssl)
        finally:
            self._connection_guard_inhibit_loop = False
            task = getattr(self, "_reconnect_task", None)
            # اگر نسخهٔ اصلی حلقه‌ای ساخت، جمعش می‌کنیم.
            if task is not None and not getattr(task, _LOOP_MARKER, False):
                task.cancel()
                self._reconnect_task = None

    setattr(_connect, _LOOP_MARKER, True)
    connection_class._connect = _connect

    async def _reset_once(self):
        """سوکت را بدون کشتن حلقهٔ دوره‌ای بازمی‌سازد."""
        running = asyncio.current_task()
        owned = getattr(self, "_reconnect_task", None)
        # ارجاع را برمی‌داریم تا disconnect() تسک جاری را cancel نکند.
        if owned is running:
            self._reconnect_task = None
        try:
            await self.disconnect()
        finally:
            if owned is running:
                self._reconnect_task = running

        await self._connect()
        self._connected = True
        loop = helpers.get_running_loop()
        self._send_task = loop.create_task(self._send_loop())
        self._recv_task = loop.create_task(self._recv_loop())

    connection_class._connection_guard_reset_once = _reset_once

    async def _reconnect_loop(self):
        try:
            while self._connected:
                await asyncio.sleep(self._reconnect_interval)
                if not self._connected:
                    break
                try:
                    await self._connection_guard_reset_once()
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    # ترنسپورت بالا نیامد. حلقه را زنده نگه می‌داریم و
                    # دوباره تلاش می‌کنیم؛ خروج از حلقه یعنی مرگ دائمی.
                    self._connected = False
                    if logger is not None:
                        logger.log_error(
                            f"CONNECTION GUARD periodic reset failed: {error!r}"
                        )
                    return
        except asyncio.CancelledError:
            pass

    setattr(_reconnect_loop, _LOOP_MARKER, True)
    connection_class._reconnect_loop = _reconnect_loop

    original_public = getattr(connection_class, "connect", None)
    if original_public is not None and not getattr(original_public, _LOOP_MARKER, False):
        async def connect(self, timeout=None, ssl=None):
            await original_public(self, timeout=timeout, ssl=ssl)
            task = getattr(self, "_reconnect_task", None)
            if task is None or task.done():
                task = asyncio.ensure_future(self._reconnect_loop())
                setattr(task, _LOOP_MARKER, True)
                self._reconnect_task = task

        setattr(connect, _LOOP_MARKER, True)
        connection_class.connect = connect

    return True


# ==========================================================================
#  ۳) سقف زمانی روی هر RPC
# ==========================================================================
class RpcTimeout(Exception):
    """یک RPC در مهلت مقرر پاسخ نگرفت."""


_RPC_MARKER = "_connection_guard_rpc_timeout"


def install_rpc_timeout(client, timeout=60.0, on_timeout=None, logger=None):
    """`client._call` را با یک سقف زمانی می‌پیچد.

    بدون این، گم شدن یک پاسخ یعنی `await` ابدی. با این، درخواست پس از
    `timeout` ثانیه شکست می‌خورد، تسکِ هندلر آزاد می‌شود و ناظر خبردار
    می‌شود تا در صورت لزوم اتصال را بازسازی کند.
    """
    original = getattr(client, "_call", None)
    if original is None or getattr(original, _RPC_MARKER, False):
        return False

    async def _call(sender, request, ordered=False, flood_sleep_threshold=None):
        try:
            return await asyncio.wait_for(
                original(
                    sender,
                    request,
                    ordered=ordered,
                    flood_sleep_threshold=flood_sleep_threshold,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            name = request.__class__.__name__
            if logger is not None:
                logger.log_error(
                    f"CONNECTION GUARD rpc timeout after {timeout}s request={name}"
                )
            if on_timeout is not None:
                on_timeout(request)
            raise RpcTimeout(f"{name} did not answer within {timeout}s") from None

    setattr(_call, _RPC_MARKER, True)
    client._call = _call
    return True


# ==========================================================================
#  ۴) بازسازی کامل کلاینت بدون ری‌استارت
# ==========================================================================
def cancel_pending_requests(client, reason=None):
    """همهٔ futureهای معلق سِندر را لغو می‌کند و تعدادشان را برمی‌گرداند."""
    sender = getattr(client, "_sender", None)
    if sender is None:
        return 0
    pending = getattr(sender, "_pending_state", None)
    if not pending:
        return 0

    error = ConnectionError(reason or "connection rebuilt")
    cancelled = 0
    for state in list(pending.values()):
        future = getattr(state, "future", None)
        if future is None or future.done():
            continue
        future.set_exception(error)
        cancelled += 1
    pending.clear()
    return cancelled


class ConnectionSupervisor:
    """ناظر سلامت اتصال؛ در صورت خرابی پایدار کلاینت را بازمی‌سازد.

    شرایط بازسازی:

    * تعداد قاب‌های کهنهٔ سشن در پنجرهٔ زمانی از حد بگذرد
      (یعنی `_state.reset()` رخ داده ولی جریان پاسخ‌ها ترمیم نشده)،
    * یا RPCها پشت سر هم timeout بخورند،
    * یا کلاینت اصلاً connected نباشد.
    """

    def __init__(
        self,
        client,
        logger=None,
        tracker=None,
        stale_threshold=20,
        timeout_threshold=3,
        check_interval=15.0,
        window=120.0,
    ):
        self.client = client
        self.logger = logger
        self.tracker = tracker or StaleSessionTracker(window)
        self.stale_threshold = stale_threshold
        self.timeout_threshold = timeout_threshold
        self.check_interval = check_interval
        self.timeouts = EventWindow(window)
        self.rebuilds = 0
        self.last_reason = None
        self._rebuilding = False

    # -- ورودی‌های رویداد ------------------------------------------------
    def note_rpc_timeout(self, request=None):
        self.timeouts.record()

    # -- تصمیم -----------------------------------------------------------
    def diagnose(self):
        """اگر بازسازی لازم است، دلیلش را برمی‌گرداند؛ وگرنه None."""
        stale = self.tracker.recent()
        if stale >= self.stale_threshold:
            return f"stale-session frames={stale} in window"

        timeouts = self.timeouts.count()
        if timeouts >= self.timeout_threshold:
            return f"rpc timeouts={timeouts} in window"

        is_connected = getattr(self.client, "is_connected", None)
        if callable(is_connected) and not is_connected():
            return "client reported not connected"

        return None

    # -- اجرا -------------------------------------------------------------
    async def rebuild(self, reason):
        """اتصال را از صفر می‌سازد: لغو معلق‌ها، قطع، وصل دوباره."""
        if self._rebuilding:
            return False
        self._rebuilding = True
        self.last_reason = reason
        try:
            self._log_error(f"CONNECTION GUARD rebuilding client: {reason}")

            cancelled = cancel_pending_requests(self.client, reason)
            if cancelled:
                self._log_info(
                    f"CONNECTION GUARD cancelled {cancelled} pending request(s)"
                )

            try:
                await self.client.disconnect()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._log_error(f"CONNECTION GUARD disconnect failed: {error!r}")

            await self.client.connect()

            self.tracker.reset()
            self.timeouts.clear()
            self.rebuilds += 1
            self._log_info("CONNECTION GUARD rebuild complete")
            return True
        finally:
            self._rebuilding = False

    async def run(self, sleep=None):
        """حلقهٔ دائمی پایش. در `run()` ربات به‌صورت task اجرا می‌شود."""
        sleeper = sleep or asyncio.sleep
        while True:
            try:
                await sleeper(self.check_interval)
                reason = self.diagnose()
                if reason:
                    await self.rebuild(reason)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._log_error(f"CONNECTION GUARD supervisor error: {error!r}")

    # -- لاگ ---------------------------------------------------------------
    def _log_info(self, message):
        if self.logger is not None:
            self.logger.log_info(message)

    def _log_error(self, message):
        if self.logger is not None:
            self.logger.log_error(message)


# ==========================================================================
#  نصب یک‌جا
# ==========================================================================
def install(client, logger=None, rpc_timeout=60.0, **supervisor_options):
    """همهٔ اصلاحات را نصب و ناظر آماده‌به‌کار را برمی‌گرداند.

    فراخوانی دوباره بی‌خطر است؛ هر وصله فقط یک بار اعمال می‌شود.
    """
    from splusthon import helpers
    from splusthon.network.mtprotostate import MTProtoState
    from splusthon.network.connection.websocket import ConnectionWebSocket

    tracker = StaleSessionTracker(supervisor_options.get("window", 120.0))
    supervisor = ConnectionSupervisor(
        client, logger=logger, tracker=tracker, **supervisor_options
    )

    install_stale_session_filter(MTProtoState, tracker, logger)
    install_periodic_reset_fix(ConnectionWebSocket, helpers, logger)
    install_rpc_timeout(
        client,
        timeout=rpc_timeout,
        on_timeout=supervisor.note_rpc_timeout,
        logger=logger,
    )
    return supervisor
