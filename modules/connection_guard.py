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
    """قاب‌های متعلق به سشن قبلی را می‌شمارد.

    علاوه بر شمارش، «آخرین باری که هر MTProto message با موفقیت رمزگشایی
    شد» را هم نگه می‌دارد (``last_data_ts``). این همان سیگنالِ «زنده بودنِ
    سوکت» است: یک اتصال سالم به‌لطف keepalive هر چند ثانیه یک Pong می‌گیرد
    و برای هر قابِ دریافتی ``decrypt_message_data`` صدا می‌شود.
    """

    def __init__(self, window=120.0):
        self.window = EventWindow(window)
        self.total = 0
        self.last_at = None
        self.last_data_ts = None

    def record(self):
        self.total += 1
        self.last_at = time.monotonic()
        return self.window.record()

    def recent(self):
        return self.window.count()

    def note_received(self):
        """ثبت دریافت هر قابِ سالم از سوکت (مبنای تشخیص مرگِ بی‌صدا)."""
        self.last_data_ts = time.monotonic()

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
            result = original(self, body)
            # حتی اگر قاب از سشن قبلی باشد، همین که یک قابِ معتبر رسیده
            # یعنی سوکت زنده است → لایو-نس را تازه نگه دار.
            tracker.note_received()
            return result
        except Exception as error:
            if not _is_wrong_session(error):
                raise
            tracker.note_received()
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
_STAMP_MARKER = "_connection_guard_stamped"


def _seen_at(sender):
    """جدول کناری «msg_id → زمان اولین مشاهده» برای یک سِندر.

    ``RequestState`` دارای ``__slots__`` است و اصلاً فیلد تازه قبول
    نمی‌کند (بررسی شد: ``AttributeError``)، پس زمان را نمی‌توان روی
    خودِ state چسباند. این جدول کنار سِندر نگه داشته می‌شود و همراه
    خودِ سِندر آزاد می‌شود.
    """
    table = getattr(sender, "_guard_seen_at", None)
    if table is None:
        table = {}
        try:
            sender._guard_seen_at = table
        except AttributeError:
            return {}
    return table


def note_pending(sender):
    """درخواست‌های معلقِ تازه را زمان‌گذاری و ورودی‌های مرده را پاک می‌کند."""
    pending = getattr(sender, "_pending_state", None)
    if pending is None:
        return
    table = _seen_at(sender)
    now = time.monotonic()
    for msg_id in pending:
        table.setdefault(msg_id, now)
    if len(table) > len(pending):
        for msg_id in [m for m in table if m not in pending]:
            table.pop(msg_id, None)


def drop_completed_pending(sender):
    """Remove sender states whose futures have already completed.

    Some SPlusthon versions leave answered keepalive/RPC states in the map
    until another receive-path sweep.  Removing only ``future.done()`` rows is
    safe and keeps reconnect from replaying completed requests.
    """
    pending = getattr(sender, "_pending_state", None)
    if not pending:
        return 0
    table = _seen_at(sender)
    removed = 0
    for msg_id, state in list(pending.items()):
        future = getattr(state, "future", None)
        if future is None or not future.done():
            continue
        pending.pop(msg_id, None)
        table.pop(msg_id, None)
        removed += 1
    return removed


def drop_stale_pending(sender, deadline):
    """درخواست‌های معلقی که از مهلت گذشته‌اند را از جدول سِندر پاک می‌کند.

    ``asyncio.wait_for`` فقط *منتظر ماندن* را لغو می‌کند؛ خودِ درخواست
    در ``sender._pending_state`` باقی می‌ماند چون آن جدول را لایهٔ
    شبکه پر می‌کند نه فراخوان. بدون پاک‌سازی، هر RPC تایم‌اوت‌خورده
    یک «زامبی» می‌شود که:

      • تا ابد در حافظه می‌ماند،
      • ``_pop_states`` را که پیمایش خطی روی همین جدول است کند می‌کند،
      • و بدتر از همه، در هر reconnect خط
        ``_send_queue.extend(self._pending_state.values())``
        همهٔ آن‌ها را دوباره روی سوکت می‌فرستد.

    خروجی: تعداد زامبی‌های پاک‌شده.
    """
    pending = getattr(sender, "_pending_state", None)
    if not pending:
        return 0

    table = _seen_at(sender)
    removed = 0
    for msg_id, state in list(pending.items()):
        started = table.get(msg_id)
        if started is None or started > deadline:
            continue
        pending.pop(msg_id, None)
        table.pop(msg_id, None)
        future = getattr(state, "future", None)
        if future is not None and not future.done():
            future.cancel()
        removed += 1
    return removed


def install_rpc_timeout(client, timeout=60.0, on_timeout=None, logger=None):
    """`client._call` را با یک سقف زمانی می‌پیچد.

    بدون این، گم شدن یک پاسخ یعنی `await` ابدی. با این، درخواست پس از
    `timeout` ثانیه شکست می‌خورد، تسکِ هندلر آزاد می‌شود و ناظر خبردار
    می‌شود تا در صورت لزوم اتصال را بازسازی کند.

    ⚠️ صرفِ `wait_for` کافی نیست و خودش نشتی می‌سازد: درخواست در
    ``sender._pending_state`` جا می‌ماند. برای همین پس از هر timeout،
    زامبی‌های همان سِندر پاک می‌شوند.
    """
    original = getattr(client, "_call", None)
    if original is None or getattr(original, _RPC_MARKER, False):
        return False

    async def _call(sender, request, ordered=False, flood_sleep_threshold=None):
        started = time.monotonic()
        task = asyncio.ensure_future(
            original(
                sender,
                request,
                ordered=ordered,
                flood_sleep_threshold=flood_sleep_threshold,
            )
        )
        # یک چرخهٔ رویداد بعد، درخواست در جدول معلق‌ها نشسته است و
        # می‌توان زمان آن را ثبت کرد.
        try:
            await asyncio.sleep(0)
            note_pending(sender)
        except Exception:
            pass
        try:
            return await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            name = request.__class__.__name__
            # هر چیزی که پیش از شروع این درخواست معلق مانده قطعاً
            # زامبی است؛ همراه با خودِ این درخواست پاک می‌شود.
            dropped = drop_stale_pending(sender, started)
            if logger is not None:
                logger.log_error(
                    f"CONNECTION GUARD rpc timeout after {timeout}s "
                    f"request={name} dropped_pending={dropped}"
                )
            if on_timeout is not None:
                on_timeout(request)
            raise RpcTimeout(f"{name} did not answer within {timeout}s") from None

    setattr(_call, _RPC_MARKER, True)
    client._call = _call
    return True


# ==========================================================================
#  ۵) سقف زمانی روی مسیر ارسال (send_bytes/drain)
# ==========================================================================
_SEND_TIMEOUT_MARKER = "_connection_guard_send_timeout"

# پیش‌فرض مهلتِ مسیر ارسال: اگر `send_bytes` بیشتر از این مدت جواب ندهد،
# به‌معنای گیر کردنِ جهتِ خروجی WebSocket است (send-side stall).
SEND_TIMEOUT_SECONDS = 20.0


def install_send_timeout(writer_class, timeout=SEND_TIMEOUT_SECONDS,
                         on_stall=None, logger=None):
    """``WebSocketWriter.drain`` را با سقف زمانی می‌پیچد.

    مسیر ارسال در SPlusthon هیچ timeout ندارد: ``Connection._send_loop``
    فقط ``await self._writer.drain()`` را صدا می‌زند و ``drain()`` هم
    ``await self._ws.send_bytes(data)`` را. اگر جهتِ خروجی سوکت (TCP
    half-open) از کار افتاده باشد، این ``await`` برای همیشه معلق می‌ماند —
    در حالی که جهتِ Receive همچنان زنده است و ربات «متصل» دیده می‌شود.

    این وصله `send_bytes` را با `asyncio.wait_for` می‌پوشاند. اگر بیش از
    مهلت جواب ندهد:
      * به supervisor خبر می‌دهد (``on_stall``) تا بازسازی/rebuild اجرا شود،
      * و یک ``TimeoutError`` بالا می‌اندازد تا ``_send_loop`` خروج بگیرد و
        اتصال بسته شود — پس supervisor می‌تواند کلاینتِ تازه بسازد.
    """
    original = getattr(writer_class, "drain", None)
    if original is None or getattr(original, _SEND_TIMEOUT_MARKER, False):
        return False

    async def drain(self):
        if not getattr(self, "_pending", None):
            return
        data = bytes(self._pending)
        self._pending.clear()
        try:
            await asyncio.wait_for(
                self._ws.send_bytes(data), timeout=timeout)
        except asyncio.TimeoutError:
            if logger is not None:
                logger.log_error(
                    "CONNECTION GUARD send timeout: "
                    f"send_bytes did not complete within {timeout}s"
                )
            if on_stall is not None:
                try:
                    on_stall()
                except Exception:
                    pass
            raise
        except asyncio.CancelledError:
            raise

    setattr(drain, _SEND_TIMEOUT_MARKER, True)
    writer_class.drain = drain
    return True


# ==========================================================================
#  بازسازی کامل کلاینت بدون ری‌استارت
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
    * یا کلاینت اصلاً connected نباشد،
    * یا حلقه‌ی دریافت بدون دلیل خارج شده باشد (`_recv_loop_handle` تمام
      شده ولی کلاینت هنوز connected است)،
    * یا برای مدت طولانی هیچ MTProto message‌ای دریافت نشده باشد
      (مرگِ بی‌صدای سوکت که هیچ‌کدام از نشانه‌های بالا را ندارد).
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
        receive_dead_threshold=180.0,
        client_factory=None,
    ):
        self.client = client
        self.logger = logger
        self.tracker = tracker or StaleSessionTracker(window)
        self.stale_threshold = stale_threshold
        self.timeout_threshold = timeout_threshold
        self.check_interval = check_interval
        self.receive_dead_threshold = receive_dead_threshold
        self.timeouts = EventWindow(window)
        self.send_stalls = EventWindow(window)
        self.rebuilds = 0
        self.last_reason = None
        self._rebuilding = False
        # کارخانهٔ ساخت کلاینتِ کاملاً جدید. اگر تنظیم باشد، rebuild به‌جای
        # connect روی همان کلاینت، یک SoroushClient تازه (سشنِ تازه، sender
        # تازه، receive loop تازه) می‌سازد و client را عوض می‌کند.
        self.client_factory = client_factory

    # -- ورودی‌های رویداد ------------------------------------------------
    def note_rpc_timeout(self, request=None):
        self.timeouts.record()

    def note_received(self):
        """ثبت دریافت یک قابِ سالم؛ به‌صورت دستی از بیرون هم قابل صدا زدن است."""
        if self.tracker is not None:
            self.tracker.note_received()

    def note_send_stall(self):
        """ثبت گیر کردنِ مسیر ارسال (send_bytes/drain timeout)."""
        self.send_stalls.record()

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

        # مرگِ بی‌صدای حلقه‌ی دریافت: هندلِ `_recv_loop` تمام شده ولی سِندر
        # هنوز خودش را متصل می‌داند و reconnectی در جریان نیست. این یعنی
        # loop خارج شده و هیچ کس آن را برنگردانده — همان «process زنده ولی
        # receive مرده».
        sender = getattr(self.client, "_sender", None)
        if sender is not None:
            recv_handle = getattr(sender, "_recv_loop_handle", None)
            user_connected = getattr(sender, "_user_connected", False)
            reconnecting = getattr(sender, "_reconnecting", False)
            if (
                recv_handle is not None
                and recv_handle.done()
                and not recv_handle.cancelled()
                and user_connected
                and not reconnecting
            ):
                return "receive loop exited unexpectedly"

        # مرگِ بی‌صدای سوکت: هیچ قابی (حتی Pong) به‌مدت طولانی نرسیده.
        # این سناریو هیچ نشانه‌ی خطایی ندارد، پس تنها سیگنال قابل‌اعتماد
        # همین «زنده بودنِ ترافیک دریافتی» است.
        if self.tracker is not None:
            last = self.tracker.last_data_ts
            if last is not None:
                idle = time.monotonic() - last
                if idle > self.receive_dead_threshold:
                    return f"no data received for {idle:.0f}s"

        # گیر کردنِ مسیر ارسال (send-side stall): اگر send_bytes/drain
        # تایم‌اوت خورده باشد، جهتِ خروجی خراب است حتی اگر Receive زنده باشد.
        if self.send_stalls.count() >= self.timeout_threshold:
            return f"send stalls={self.send_stalls.count()} in window"

        # مرگِ حلقهٔ ارسال: هندلِ `_send_loop` تمام شده (یا Connection
        # send_task تمام شده) ولی سِندر هنوز خودش را متصل می‌داند و reconnectی
        # در جریان نیست. این یعنی directionِ خروجی مرده ولی ورودی زنده است.
        sender = getattr(self.client, "_sender", None)
        if sender is not None:
            user_connected = getattr(sender, "_user_connected", False)
            reconnecting = getattr(sender, "_reconnecting", False)
            send_handle = getattr(sender, "_send_loop_handle", None)
            if (
                send_handle is not None
                and send_handle.done()
                and not send_handle.cancelled()
                and user_connected
                and not reconnecting
            ):
                return "send loop exited unexpectedly"
            # Connection-level send task: جایی که drain/send_bytes اجرا می‌شود
            conn = getattr(sender, "_connection", None)
            if conn is not None:
                send_task = getattr(conn, "_send_task", None)
                if (
                    send_task is not None
                    and send_task.done()
                    and not send_task.cancelled()
                    and user_connected
                    and not reconnecting
                ):
                    return "connection send task exited unexpectedly"

        return None

    # -- اجرا -------------------------------------------------------------
    async def verify(self):
        """بررسی می‌کند اتصال واقعاً سالم است یا نه.

        سه شرط: کلاینت connected باشد، یک RPC آزمایشی جواب بدهد، و حلقهٔ
        دریافت (receive loop) دوباره فعال باشد. True یعنی آمادهٔ دریافت.
        """
        is_connected = getattr(self.client, "is_connected", None)
        if callable(is_connected) and not is_connected():
            self._log_error("CONNECTION GUARD verify: client not connected")
            return False

        # ۱) RPC آزمایشی: چند درخواست ساده که پاسخ کوتاه می‌دهد.
        # اگر کلاینت `get_me` نداشته باشد (مثل کلاینت قلابیِ تست‌ها)، از
        # این مرحله رد می‌شویم؛ روی کلاینت واقعی SPlusthon موجود است.
        get_me = getattr(self.client, "get_me", None)
        if callable(get_me):
            try:
                await asyncio.wait_for(get_me(), timeout=15.0)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._log_error(
                    f"CONNECTION GUARD verify: test RPC failed ({error!r})"
                )
                return False

        # ۲) حلقهٔ دریافت زنده است.
        sender = getattr(self.client, "_sender", None)
        if sender is not None:
            recv_handle = getattr(sender, "_recv_loop_handle", None)
            if recv_handle is not None and recv_handle.done():
                self._log_error(
                    "CONNECTION GUARD verify: receive loop not running"
                )
                return False

            # ۳) حلقهٔ ارسال هم زنده باشد (جهتِ خروجی سالم).
            send_handle = getattr(sender, "_send_loop_handle", None)
            if send_handle is not None and send_handle.done():
                self._log_error(
                    "CONNECTION GUARD verify: send loop not running"
                )
                return False
            # Connection-level send task (جایی که drain/send_bytes است)
            conn = getattr(sender, "_connection", None)
            if conn is not None:
                send_task = getattr(conn, "_send_task", None)
                if send_task is not None and send_task.done():
                    self._log_error(
                        "CONNECTION GUARD verify: connection send task "
                        "not running"
                    )
                    return False

        self._log_info("CONNECTION GUARD verify: OK")
        return True

    async def rebuild(self, reason):
        """اتصال را از صفر می‌سازد.

        اگر ``client_factory`` تنظیم باشد، به‌جای connect روی همان کلاینتِ
        کهنه، یک ``SoroushClient`` کاملاً جدید (سشن تازه، sender تازه،
        receive loop تازه) ساخته می‌شود و ``self.client`` عوض می‌شود. در
        غیر این صورت (برای تست) روی همان کلاینت disconnect/connect انجام
        می‌شود.

        بعد از ساخت، با ``verify`` تأیید می‌شود که واقعاً آمادهٔ دریافت است.
        """
        if self._rebuilding:
            return False
        self._rebuilding = True
        self.last_reason = reason
        old_client = self.client
        try:
            self._log_error(f"CONNECTION GUARD rebuilding client: {reason}")

            cancelled = cancel_pending_requests(old_client, reason)
            if cancelled:
                self._log_info(
                    f"CONNECTION GUARD cancelled {cancelled} pending request(s)"
                )

            # همیشه کلاینت کهنه را کامل می‌بندیم تا WebSocket/Sender/Receive
            # Loop/Taskهای قدیمی متوقف شوند و Sessionِ خراب دوباره استفاده نشود.
            try:
                await old_client.disconnect()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._log_error(
                    f"CONNECTION GUARD old client disconnect failed: {error!r}"
                )

            new_client = old_client
            if self.client_factory is not None:
                new_client = await self.client_factory(old_client, reason)
                if new_client is None:
                    self._log_error(
                        "CONNECTION GUARD rebuild: client_factory returned None"
                    )
                    return False
                self.client = new_client
            else:
                # بدون factory (مثلاً در تست): روی همان کلاینت disconnect+connect
                try:
                    await old_client.connect()
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self._log_error(
                        f"CONNECTION GUARD reconnect failed: {error!r}"
                    )
                    return False

            # تأیید: فقط اگر اتصالِ جدید واقعاً سالم باشد بازسازی موفق است.
            ok = await self.verify()
            if not ok:
                self._log_error("CONNECTION GUARD rebuild: verify FAILED")
                return False

            self.tracker.reset()
            self.tracker.note_received()
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
    from splusthon.network.connection.websocket import (
        ConnectionWebSocket,
        WebSocketWriter,
    )

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
    # سقف زمانی روی مسیر ارسال تا «send-side stall» دیگر ربات را بی‌صدا نکند.
    send_timeout = supervisor_options.get("send_timeout", SEND_TIMEOUT_SECONDS)
    install_send_timeout(
        WebSocketWriter,
        timeout=send_timeout,
        on_stall=supervisor.note_send_stall,
        logger=logger,
    )
    return supervisor
