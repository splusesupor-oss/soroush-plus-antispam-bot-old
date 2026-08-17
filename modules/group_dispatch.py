"""Per-group incoming-message dispatcher with isolated lanes.

SPlusthon starts a task for every NewMessage.  A spam wave in one chat then
spawns hundreds of concurrent handlers that all fight for the same RPC
sender, so admin commands stall.

This dispatcher keeps **isolated workers per (chat_id, lane)**:

* ``admin``     — owner/moderation commands; never dropped; 1 worker per chat (serial, preserves order)
* ``command``   — public/user commands (help, games, shop); never dropped; 1 worker per chat
* ``normal``    — ordinary chat / spam; capped by ``max_pending_normal``; **4 concurrent workers per chat**

Lanes of the same group run at the same time, so mute/ban/lock do not wait
for a heavy normal job.  Different chats stay independent.
Normal lane uses multiple workers per chat so a burst in one chat
(15×150ms) is absorbed in ~600ms instead of ~2200ms (queue_wait 2.2s → ~450ms).

Heavy background work (spam cleanup, moderation callbacks, notice expiry,
delete batches, flush) never goes through this dispatcher; each has its
own per-chat queue/worker and is fire-and-forget via ``asyncio.create_task``
so it cannot fill the normal message queue.

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

    # Do not park a ready job behind another lane of the same chat.
    # Admin / command / normal already have separate workers; extra
    # yield only added queue_wait after Soroush had already answered.
    HIGHER_LANE_WAIT_SECONDS = 0.0

    def __init__(self, *, max_pending_normal=40, logger=None, normal_concurrency=4):
        self.max_pending_normal = int(max_pending_normal)
        self.normal_concurrency = int(normal_concurrency) if int(normal_concurrency) > 0 else 1
        self.logger = logger
        self._queues = {}
        # key -> list[Task]  (normal lane may have up to normal_concurrency workers)
        self._workers = {}
        self._normal_pending = {}
        self._busy = set()
        self._busy_counts = {}
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
        return sum(
            sum(1 for t in lst if t is not None and not t.done())
            for lst in self._workers.values()
        )

    def _lane_key(self, chat_id, lane):
        return (chat_id, lane)

    def _desired_concurrency(self, lane):
        if lane == LANE_NORMAL:
            return self.normal_concurrency
        return 1

    def _alive_workers(self, key):
        lst = self._workers.get(key)
        if not lst:
            return []
        return [t for t in lst if t is not None and not t.done()]

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

        # Ensure enough workers for this lane (normal: up to normal_concurrency)
        workers = self._workers.get(key)
        if workers is None:
            workers = []
            self._workers[key] = workers
        # Prune done workers
        workers[:] = [t for t in workers if not t.done()]
        desired = self._desired_concurrency(lane)
        alive = len(workers)
        # Spawn if we have fewer than desired and queue has work.
        # For normal lane this scales quickly under burst (15 messages → 3 workers).
        if alive < desired:
            # For normal, spawn one per submit until desired is reached;
            # for admin/command, spawn only if none alive.
            # Also, if queue depth exceeds alive, we may need more.
            needed = desired - alive
            # If queue is deep, spawn up to needed at once (not just 1)
            # but cap to 1 per submit to avoid thundering herd on first burst.
            # We spawn 1 per submit which converges in 3 submits for normal.
            workers.append(asyncio.create_task(
                self._worker(chat_id, lane, queue)
            ))
            # If the burst enqueued 15 at once before any worker started,
            # the first worker will see a deep queue; it could still benefit
            # from extra workers, but the next submits will spawn them.
            # To handle a single bulk submit, check depth:
            if lane == LANE_NORMAL and queue.qsize() > len(workers) * 2 and len(workers) < desired:
                # Queue is still deep after spawning one, spawn one more immediately
                # (up to desired). This handles the case where 15 were enqueued
                # with a single submit loop that reuses same event loop tick.
                while len(workers) < desired and queue.qsize() > len(workers):
                    workers.append(asyncio.create_task(
                        self._worker(chat_id, lane, queue)
                    ))
        elif not workers:
            workers.append(asyncio.create_task(
                self._worker(chat_id, lane, queue)
            ))
        return True

    async def _worker(self, chat_id, lane, queue):
        if self.logger is not None:
            self.logger.log_info(
                f"GROUP DISPATCH WORKER START chat_id={chat_id} lane={lane}"
            )
        key = self._lane_key(chat_id, lane)
        try:
            while True:
                try:
                    item = await queue.get()
                except asyncio.CancelledError:
                    raise
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
                # Track busy counts for accurate _lane_busy with concurrency
                self._busy.add(key)
                self._busy_counts[key] = self._busy_counts.get(key, 0) + 1
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
                    cnt = self._busy_counts.get(key, 1) - 1
                    if cnt <= 0:
                        self._busy_counts.pop(key, None)
                        self._busy.discard(key)
                    else:
                        self._busy_counts[key] = cnt
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
                    # Give a tiny window for a burst that is still being
                    # enqueued in this same tick.  Without this, a 15-message
                    # burst enqueued in a tight loop would be seen as empty
                    # by the first worker after its first item, causing it to
                    # exit before the remaining 14 are drained by the extra
                    # workers (which would then also exit early).
                    await asyncio.sleep(0)
                    if queue.empty():
                        return
        finally:
            # Remove this worker from the list
            lst = self._workers.get(key)
            if lst is not None:
                try:
                    lst.remove(asyncio.current_task())
                except ValueError:
                    pass
                if not lst:
                    self._workers.pop(key, None)
                    # Only pop queue if truly empty (another worker may have just enqueued)
                    if queue.empty():
                        self._queues.pop(key, None)
                        if lane == LANE_NORMAL:
                            self._normal_pending.pop(chat_id, None)
            self._busy.discard(key)
            self._busy_counts.pop(key, None)

    def _lane_busy(self, chat_id, lane):
        key = self._lane_key(chat_id, lane)
        if key in self._busy:
            return True
        queue = self._queues.get(key)
        return bool(queue is not None and queue.qsize() > 0)

    async def _yield_to_higher_lanes(self, chat_id, lane):
        """Kept for log compatibility. Never sleeps; workers stay independent."""
        return 0.0

    async def join(self, timeout=None):
        """Wait until every queued job has finished (tests / shutdown)."""
        async def _wait():
            while True:
                queues = [queue for queue in self._queues.values() if queue.qsize()]
                workers = []
                for lst in self._workers.values():
                    workers.extend([t for t in lst if not t.done()])
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
        workers = []
        for lst in self._workers.values():
            workers.extend(lst)
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        self._queues.clear()
        self._normal_pending.clear()
        self._busy.clear()
        self._busy_counts.clear()

    def reset_for_tests(self):
        self._queues.clear()
        self._workers.clear()
        self._normal_pending.clear()
        self._busy.clear()
        self._busy_counts.clear()
        self._seq = 0
        self._closed = False
        for key in self.stats:
            self.stats[key] = 0
