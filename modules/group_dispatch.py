"""Per-group incoming-message dispatcher with isolated GroupContext.

Each ``chat_id`` owns a ``GroupContext``: its own queues and workers.
A 5-second job in group A never holds the queue or worker of group B.

Inside a group, two persistent workers share one priority scheme:

* ``control`` — admin/moderation (ban/kick/lock) and user commands
* ``normal``  — ordinary chat / spam; capped by ``max_pending_normal``

Command/moderation therefore never wait behind an in-flight normal job
of the same chat.  Workers exit when idle so inactive groups release
tasks.  Classification is text-only: no await, no RPC, no file I/O.

Lanes of different chats never share a lock.  The only remaining global
resource is the single SPlusthon sender; handlers must not start extra
RPCs (get_entity / get_permissions) on the normal path.
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
LANE_CONTROL = "control"

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


def worker_lane_for(priority, kind=None):
    """Map a job onto the two per-chat workers: control vs normal."""
    lane = lane_for(priority, kind)
    if lane == LANE_NORMAL:
        return LANE_NORMAL
    return LANE_CONTROL


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


class GroupContext:
    """Isolated runtime for one chat: own queues, workers, counters."""

    __slots__ = (
        "chat_id", "queues", "workers", "normal_pending",
        "last_active", "busy",
    )

    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.queues = {}
        self.workers = {}
        self.normal_pending = 0
        self.last_active = time.monotonic()
        self.busy = set()

    def is_idle(self):
        if self.busy:
            return False
        if self.normal_pending:
            return False
        for task in self.workers.values():
            if task is not None and not task.done():
                return False
        for queue in self.queues.values():
            if queue.qsize():
                return False
        return True


class GroupDispatcher:
    """One GroupContext per chat; control and normal workers never share a lock."""

    def __init__(self, *, max_pending_normal=40, logger=None):
        self.max_pending_normal = int(max_pending_normal)
        self.logger = logger
        self._contexts = {}
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

    def _context(self, chat_id):
        ctx = self._contexts.get(chat_id)
        if ctx is None:
            ctx = GroupContext(chat_id)
            self._contexts[chat_id] = ctx
        ctx.last_active = time.monotonic()
        return ctx

    def pending_normal(self, chat_id):
        ctx = self._contexts.get(chat_id)
        return 0 if ctx is None else int(ctx.normal_pending)

    def queue_size(self, chat_id):
        ctx = self._contexts.get(chat_id)
        if ctx is None:
            return 0
        return sum(queue.qsize() for queue in ctx.queues.values())

    def worker_count(self):
        total = 0
        for ctx in self._contexts.values():
            total += sum(
                1 for task in ctx.workers.values()
                if task is not None and not task.done()
            )
        return total

    def context_count(self):
        return len(self._contexts)

    def submit(self, chat_id, factory, *, priority=PRIORITY_NORMAL, kind="normal",
               on_overflow=None):
        """Enqueue ``factory()`` on this chat's context.  Never awaits."""
        if self._closed:
            return False
        if chat_id is None:
            chat_id = 0
        lane = lane_for(priority, kind)
        worker_lane = worker_lane_for(priority, kind)
        ctx = self._context(chat_id)
        if worker_lane == LANE_NORMAL:
            if ctx.normal_pending >= self.max_pending_normal:
                self.stats["dropped"] += 1
                if self.logger is not None:
                    self.logger.log_info(
                        "GROUP DISPATCH OVERFLOW "
                        f"chat_id={chat_id} pending={ctx.normal_pending}"
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

        queue = ctx.queues.get(worker_lane)
        if queue is None:
            queue = asyncio.PriorityQueue()
            ctx.queues[worker_lane] = queue
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
            ctx.normal_pending += 1
            self.stats["normal"] += 1

        self._ensure_worker(ctx, worker_lane, queue)
        return True

    def _ensure_worker(self, ctx, worker_lane, queue):
        """Start the persistent per-chat worker if it is missing.

        ``submit`` is sync and may be called from tests with no running
        loop.  In that case the job stays queued until a loop exists.
        """
        worker = ctx.workers.get(worker_lane)
        if worker is not None and not worker.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        ctx.workers[worker_lane] = loop.create_task(
            self._worker(ctx, worker_lane, queue)
        )

    async def _worker(self, ctx, worker_lane, queue):
        chat_id = ctx.chat_id
        if self.logger is not None:
            self.logger.log_info(
                f"GROUP DISPATCH WORKER START chat_id={chat_id} lane={worker_lane}"
            )
        try:
            while True:
                item = await queue.get()
                if len(item) == 5:
                    priority, _seq, kind, factory, enqueued_at = item
                else:
                    priority, _seq, kind, factory = item
                    enqueued_at = time.perf_counter()
                if worker_lane == LANE_NORMAL:
                    ctx.normal_pending = max(0, ctx.normal_pending - 1)
                started = time.perf_counter()
                queue_wait_ms = (started - enqueued_at) * 1000
                ctx.busy.add(worker_lane)
                ctx.last_active = time.monotonic()
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
                            f"chat_id={chat_id} lane={worker_lane} kind={kind} "
                            f"error={error!r}"
                        )
                finally:
                    ctx.busy.discard(worker_lane)
                    queue.task_done()
                    if self.logger is not None:
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        if queue_wait_ms >= 50:
                            self.logger.log_info(
                                "QUEUE WAIT TIME "
                                f"chat_id={chat_id} lane={worker_lane} kind={kind} "
                                f"queue_wait_ms={queue_wait_ms:.1f} yield_ms=0.0"
                            )
                        if elapsed_ms >= 100 or worker_lane != LANE_NORMAL:
                            self.logger.log_info(
                                "HANDLER TIME "
                                f"chat_id={chat_id} lane={worker_lane} kind={kind} "
                                f"handler_ms={elapsed_ms:.1f}"
                            )
                            self.logger.log_info(
                                "GROUP DISPATCH JOB "
                                f"chat_id={chat_id} lane={worker_lane} kind={kind} "
                                f"priority={priority} ms={elapsed_ms:.1f}"
                            )
                if queue.empty():
                    return
        finally:
            ctx.busy.discard(worker_lane)
            if ctx.workers.get(worker_lane) is asyncio.current_task():
                ctx.workers.pop(worker_lane, None)
            # A submit may have raced the idle exit. Keep a worker if
            # work is waiting so the job is not orphaned.
            if not self._closed and queue.qsize():
                self._ensure_worker(ctx, worker_lane, queue)
                return
            if queue.empty():
                ctx.queues.pop(worker_lane, None)
            if ctx.is_idle():
                self._contexts.pop(chat_id, None)

    async def join(self, timeout=None):
        """Wait until every queued job has finished (tests / shutdown)."""
        async def _wait():
            while True:
                queues = []
                workers = []
                for ctx in list(self._contexts.values()):
                    queues.extend(
                        queue for queue in ctx.queues.values() if queue.qsize()
                    )
                    workers.extend(
                        task for task in ctx.workers.values()
                        if task is not None and not task.done()
                    )
                if not queues and not workers:
                    return
                for ctx in list(self._contexts.values()):
                    for queue in list(ctx.queues.values()):
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
        for ctx in list(self._contexts.values()):
            workers.extend(
                task for task in ctx.workers.values()
                if task is not None
            )
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._contexts.clear()

    def reset_for_tests(self):
        self._contexts.clear()
        self._seq = 0
        self._closed = False
        for key in self.stats:
            self.stats[key] = 0
