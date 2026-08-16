"""Per-group incoming-message dispatcher with isolated lanes.

SPlusthon starts a task for every NewMessage.  A spam wave in one chat then
spawns hundreds of concurrent handlers that all fight for the same RPC
sender, so admin commands stall.

This dispatcher keeps **one worker + one queue per (chat_id, lane)**:

* ``admin``     — owner/moderation commands; never dropped; own worker
* ``command``   — public/user commands (help, games, shop); never dropped
* ``normal``    — ordinary chat / spam; capped by ``max_pending_normal``

Lanes of the same group run at the same time, so mute/ban/lock do not wait
for a heavy normal job.  Different chats stay independent.

Classification is text-only: no await, no RPC, no file I/O.
"""
import asyncio
import inspect
import time

PRIORITY_ADMIN = 0
PRIORITY_COMMAND = 1
PRIORITY_NORMAL = 2

LANE_ADMIN = "admin"
LANE_COMMAND = "command"
LANE_NORMAL = "normal"

# Exact Persian admin/owner commands.
_ADMIN_EXACT = frozenset({
    "بن", "اخراج", "قفل", "باز", "پاک",
    "سکوت", "رفع سکوت", "آزاد", "اخطار",
    "ثبت ادمین", "لغو ادمین", "برکناری ادمین",
    "فعال", "غیر فعال", "فعال سازی",
    "ثبت گروه", "حذف گروه", "ثبت مالک", "لغو مالک", "برکناری مالک",
    "لیست انقضا", "صفر",
    "هوش مصنوعی فعال", "هوش مصنوعی خاموش",
    "مجاز", "غیرمجاز", "غیر مجاز", "لیست هوش مصنوعی",
    "پاکسازی خودکار", "لاگ مدیریتی",
    "ثبت قوانین", "حذف قوانین",
    "ریست آمار", "ریست اخراجی ها",
    "حذف اخطار", "حذف اخطارها",
    "اطلاع رسانی", "تایید", "✅ تایید", "لغو", "❌ لغو",
    "لیست ادمین", "لیست ادمینی",
    "سنجاق",
    "فعال کلمات ممنوعه", "لغو کلمات ممنوعه",
    "سابقه ها", "سابقه‌ها",
})

_ADMIN_PREFIXES = (
    "پاک ", "بن ", "اخراج ", "سکوت ",
    "ثبت ادمین", "لغو ادمین", "برکناری ادمین",
    "مجاز ", "غیر مجاز", "غیرمجاز",
    "!", "/", ".",
)

# Public / user commands.  Checked only after admin so «ثبت ادمین» stays admin.
_COMMAND_EXACT = frozenset({
    "راهنما", "help",
    "لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "بازی ها", "بازی‌ها",
    "لیست کاربران",
    "موجودی", "فروشگاه", "انتقال سکه",
    "رتبه ها", "رتبه‌ها", "امتیاز من", "راهنمای امتیاز",
    "آمارم", "آمار گپ", "آمار گروه",
    "بیوگرافی", "جک", "دانستنی", "ترجمه", "یاد آوری",
    "حافظه من", "حذف اسم", "قوانین",
    "حدس ایموجی", "حدس جمله", "ساخت جمله", "معما", "حدس پرچم",
    "مین یاب", "بهترین جواب", "نبرد", "بخند یا بباز",
    "جعبه شانسی", "خون آشام", "خون‌آشام",
    "اسم فامیل", "چهار گزینه ای", "جای خالی", "چیستان", "تصحیح کلمات",
    "جرعت", "جرات", "جرئت", "حقیقت", "حقیقت بگو",
    "ربات", "روباه",
    "سطح گروه", "پیام سنجاق",
    "تست دکمه", "دانلود عکس",
    "ثبت اصل", "اصلم",
})

_COMMAND_PREFIXES = (
    "ثبت اسم ", "شخصیت ", "فونت ", "جستجو ",
)

_LINK_MARKERS = (
    "http://", "https://", "www.", "t.me/", "telegram.me/",
    "splus.ir", "sapp.ir", "soroush.ir",
)


def normalize_dispatch_text(text):
    if not text:
        return ""
    value = str(text).replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    value = value.replace("ي", "ی").replace("ك", "ک")
    return " ".join(value.split())


def classify_priority(text, event=None):
    """Return ``(priority, kind)`` from the message text alone."""
    raw = normalize_dispatch_text(text)
    if not raw:
        return PRIORITY_NORMAL, LANE_NORMAL
    if raw in _ADMIN_EXACT:
        return PRIORITY_ADMIN, LANE_ADMIN
    if raw.startswith(_ADMIN_PREFIXES):
        return PRIORITY_ADMIN, LANE_ADMIN
    if raw in _COMMAND_EXACT:
        return PRIORITY_COMMAND, LANE_COMMAND
    if raw.startswith(_COMMAND_PREFIXES):
        return PRIORITY_COMMAND, LANE_COMMAND
    return PRIORITY_NORMAL, LANE_NORMAL


def lane_for(priority, kind=None):
    if kind == LANE_ADMIN or int(priority) <= PRIORITY_ADMIN:
        return LANE_ADMIN
    if kind == LANE_COMMAND or int(priority) == PRIORITY_COMMAND:
        return LANE_COMMAND
    return LANE_NORMAL


def looks_like_link(text):
    value = str(text or "").lower()
    if any(marker in value for marker in _LINK_MARKERS):
        return True
    return any(ext in value for ext in (".com/", ".ir/", ".net/", ".org/"))


def _message_bits(event):
    message = getattr(event, "message", None)
    chat_id = getattr(event, "chat_id", None)
    message_id = getattr(message, "id", None) if message is not None else None
    text = ""
    if message is not None:
        text = getattr(message, "message", None) or getattr(message, "caption", None) or ""
    user_id = getattr(event, "sender_id", None)
    if user_id is None:
        sender = getattr(event, "sender", None)
        user_id = getattr(sender, "id", None)
    return chat_id, message_id, user_id, text


class GroupDispatcher:
    """Independent admin / command / normal workers per chat."""

    # Lower lanes pause while a higher lane of the same chat is running or
    # queued, so a normal/command RPC cannot occupy the shared sender ahead
    # of mute/ban/lock.  A safety timeout prevents a hung admin from freezing
    # ordinary chat forever.
    HIGHER_LANE_WAIT_SECONDS = 15.0

    def __init__(self, *, max_pending_normal=40, logger=None):
        self.max_pending_normal = int(max_pending_normal)
        self.logger = logger
        self._queues = {}
        self._workers = {}
        self._normal_pending = {}
        self._busy = set()
        self._seq = 0
        self._closed = False
        self.stats = {
            "submitted": 0,
            "admin": 0,
            "command": 0,
            "normal": 0,
            "dropped": 0,
            "processed": 0,
            "failed": 0,
        }

    def pending_normal(self, chat_id):
        return int(self._normal_pending.get(chat_id, 0))

    def queue_size(self, chat_id):
        total = 0
        for (stored_chat, _lane), queue in self._queues.items():
            if stored_chat == chat_id:
                total += queue.qsize()
        return total

    def worker_count(self):
        return sum(1 for task in self._workers.values() if task is not None and not task.done())

    def _lane_key(self, chat_id, lane):
        return (chat_id, lane)

    def submit(self, chat_id, factory, *, priority=PRIORITY_NORMAL, kind="normal",
               on_overflow=None):
        """Enqueue ``factory()`` on the matching lane.  Never awaits."""
        if self._closed:
            return False
        if chat_id is None:
            chat_id = 0
        lane = lane_for(priority, kind)
        if lane == LANE_NORMAL:
            if self._normal_pending.get(chat_id, 0) >= self.max_pending_normal:
                self.stats["dropped"] += 1
                if self.logger is not None:
                    self.logger.log_info(
                        "GROUP DISPATCH OVERFLOW "
                        f"chat_id={chat_id} pending={self._normal_pending.get(chat_id, 0)}"
                    )
                if on_overflow is not None:
                    try:
                        on_overflow()
                    except Exception as error:
                        if self.logger is not None:
                            self.logger.log_error(
                                f"GROUP DISPATCH OVERFLOW CALLBACK FAILED "
                                f"chat_id={chat_id} error={error!r}"
                            )
                return False

        key = self._lane_key(chat_id, lane)
        queue = self._queues.get(key)
        if queue is None:
            queue = asyncio.PriorityQueue()
            self._queues[key] = queue
        self._seq += 1
        queue.put_nowait(
            (int(priority), self._seq, kind or lane, factory, time.perf_counter())
        )
        self.stats["submitted"] += 1
        if lane == LANE_ADMIN:
            self.stats["admin"] += 1
        elif lane == LANE_COMMAND:
            self.stats["command"] += 1
        else:
            self._normal_pending[chat_id] = self._normal_pending.get(chat_id, 0) + 1
            self.stats["normal"] += 1

        worker = self._workers.get(key)
        if worker is None or worker.done():
            self._workers[key] = asyncio.create_task(
                self._worker(chat_id, lane, queue)
            )
        return True

    async def _worker(self, chat_id, lane, queue):
        if self.logger is not None:
            self.logger.log_info(
                f"GROUP DISPATCH WORKER START chat_id={chat_id} lane={lane}"
            )
        key = self._lane_key(chat_id, lane)
        try:
            while True:
                item = await queue.get()
                if len(item) == 5:
                    priority, _seq, kind, factory, enqueued_at = item
                else:
                    priority, _seq, kind, factory = item
                    enqueued_at = time.perf_counter()
                if lane == LANE_NORMAL:
                    current = self._normal_pending.get(chat_id, 1)
                    self._normal_pending[chat_id] = max(0, current - 1)
                yield_ms = await self._yield_to_higher_lanes(chat_id, lane)
                started = time.perf_counter()
                queue_wait_ms = (started - enqueued_at) * 1000
                self._busy.add(key)
                try:
                    result = factory() if factory is not None else None
                    if inspect.isawaitable(result):
                        await result
                    self.stats["processed"] += 1
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self.stats["failed"] += 1
                    if self.logger is not None:
                        self.logger.log_error(
                            "GROUP DISPATCH JOB FAILED "
                            f"chat_id={chat_id} lane={lane} kind={kind} error={error!r}"
                        )
                finally:
                    self._busy.discard(key)
                    queue.task_done()
                    if self.logger is not None:
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        if queue_wait_ms >= 50:
                            self.logger.log_info(
                                "QUEUE WAIT TIME "
                                f"chat_id={chat_id} lane={lane} kind={kind} "
                                f"queue_wait_ms={queue_wait_ms:.1f} "
                                f"yield_ms={yield_ms:.1f}"
                            )
                        if elapsed_ms >= 100 or lane != LANE_NORMAL:
                            self.logger.log_info(
                                "HANDLER TIME "
                                f"chat_id={chat_id} lane={lane} kind={kind} "
                                f"handler_ms={elapsed_ms:.1f}"
                            )
                            self.logger.log_info(
                                "GROUP DISPATCH JOB "
                                f"chat_id={chat_id} lane={lane} kind={kind} "
                                f"priority={priority} ms={elapsed_ms:.1f}"
                            )
                if queue.empty():
                    return
        finally:
            self._busy.discard(key)
            if self._workers.get(key) is asyncio.current_task():
                self._workers.pop(key, None)
            if queue.empty():
                self._queues.pop(key, None)
                if lane == LANE_NORMAL:
                    self._normal_pending.pop(chat_id, None)

    def _lane_busy(self, chat_id, lane):
        key = self._lane_key(chat_id, lane)
        if key in self._busy:
            return True
        queue = self._queues.get(key)
        return bool(queue is not None and queue.qsize() > 0)

    async def _yield_to_higher_lanes(self, chat_id, lane):
        """Pause this worker while a higher-priority lane of the same chat is busy."""
        if lane == LANE_ADMIN:
            return 0.0
        started = time.perf_counter()
        deadline = started + self.HIGHER_LANE_WAIT_SECONDS
        while time.perf_counter() < deadline:
            admin_busy = self._lane_busy(chat_id, LANE_ADMIN)
            command_busy = (
                lane == LANE_NORMAL and self._lane_busy(chat_id, LANE_COMMAND)
            )
            if not admin_busy and not command_busy:
                break
            await asyncio.sleep(0.02)
        return (time.perf_counter() - started) * 1000

    async def join(self, timeout=None):
        """Wait until every queued job has finished (tests / shutdown)."""
        async def _wait():
            while True:
                queues = [queue for queue in self._queues.values() if queue.qsize()]
                workers = [task for task in self._workers.values() if not task.done()]
                if not queues and not workers:
                    return
                for queue in list(self._queues.values()):
                    await queue.join()
                if workers:
                    await asyncio.gather(*workers, return_exceptions=True)
                await asyncio.sleep(0)

        if timeout is None:
            await _wait()
            return True
        try:
            await asyncio.wait_for(_wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def close(self):
        self._closed = True
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        self._queues.clear()
        self._normal_pending.clear()
        self._busy.clear()

    def reset_for_tests(self):
        self._queues.clear()
        self._workers.clear()
        self._normal_pending.clear()
        self._busy.clear()
        self._seq = 0
        self._closed = False
        for key in self.stats:
            self.stats[key] = 0
