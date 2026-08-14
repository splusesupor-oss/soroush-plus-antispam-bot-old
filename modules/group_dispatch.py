"""Per-group incoming-message dispatcher.

SPlusthon starts a task for every NewMessage.  A spam wave in one chat then
spawns hundreds of concurrent handlers that all fight for the same RPC
sender, so admin commands in *other* groups stall.

This dispatcher keeps one worker and one priority queue per chat_id:

* admin/moderation commands are priority 0 and are never dropped
* ordinary messages (including link/spam) are priority 1
* a per-group pending cap drops extra ordinary work; the caller can still
  enqueue a delete for the overflowed message
* workers of different chats run independently

The event handler must only classify + submit, then return.
"""
import asyncio
import inspect
import time

PRIORITY_ADMIN = 0
PRIORITY_NORMAL = 1

# Exact Persian admin/owner commands.  Classification is text-only and must
# stay cheap: no await, no RPC, no file I/O.
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
})

_ADMIN_PREFIXES = (
    "پاک ", "بن ", "اخراج ", "سکوت ",
    "ثبت ادمین", "لغو ادمین", "برکناری ادمین",
    "مجاز ", "غیر مجاز", "غیرمجاز",
    "!", "/", ".",
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
        return PRIORITY_NORMAL, "normal"
    if raw in _ADMIN_EXACT:
        return PRIORITY_ADMIN, "admin"
    if raw.startswith(_ADMIN_PREFIXES):
        return PRIORITY_ADMIN, "admin"
    return PRIORITY_NORMAL, "normal"


def looks_like_link(text):
    value = str(text or "").lower()
    if any(marker in value for marker in _LINK_MARKERS):
        return True
    # Bare domains that the detector also treats as links.
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
    """One priority queue + one worker per chat."""

    def __init__(self, *, max_pending_normal=40, logger=None):
        self.max_pending_normal = int(max_pending_normal)
        self.logger = logger
        self._queues = {}
        self._workers = {}
        self._normal_pending = {}
        self._seq = 0
        self._closed = False
        self.stats = {
            "submitted": 0,
            "admin": 0,
            "normal": 0,
            "dropped": 0,
            "processed": 0,
            "failed": 0,
        }

    def pending_normal(self, chat_id):
        return int(self._normal_pending.get(chat_id, 0))

    def queue_size(self, chat_id):
        queue = self._queues.get(chat_id)
        return 0 if queue is None else queue.qsize()

    def worker_count(self):
        return sum(1 for task in self._workers.values() if task is not None and not task.done())

    def submit(self, chat_id, factory, *, priority=PRIORITY_NORMAL, kind="normal",
               on_overflow=None):
        """Enqueue ``factory()`` for ``chat_id``.  Never awaits.

        ``factory`` must return an awaitable (or None).  Returns True if the
        job was queued, False if an ordinary job was dropped by the cap.
        """
        if self._closed:
            return False
        if chat_id is None:
            chat_id = 0
        if priority > PRIORITY_ADMIN:
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

        queue = self._queues.get(chat_id)
        if queue is None:
            queue = asyncio.PriorityQueue()
            self._queues[chat_id] = queue
        self._seq += 1
        queue.put_nowait((int(priority), self._seq, kind, factory))
        self.stats["submitted"] += 1
        if priority <= PRIORITY_ADMIN:
            self.stats["admin"] += 1
        else:
            self._normal_pending[chat_id] = self._normal_pending.get(chat_id, 0) + 1
            self.stats["normal"] += 1

        worker = self._workers.get(chat_id)
        if worker is None or worker.done():
            self._workers[chat_id] = asyncio.create_task(
                self._worker(chat_id, queue)
            )
        return True

    async def _worker(self, chat_id, queue):
        if self.logger is not None:
            self.logger.log_info(f"GROUP DISPATCH WORKER START chat_id={chat_id}")
        try:
            while True:
                priority, _seq, kind, factory = await queue.get()
                if priority > PRIORITY_ADMIN:
                    current = self._normal_pending.get(chat_id, 1)
                    self._normal_pending[chat_id] = max(0, current - 1)
                started = time.perf_counter()
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
                            f"chat_id={chat_id} kind={kind} error={error!r}"
                        )
                finally:
                    queue.task_done()
                    if self.logger is not None:
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        if elapsed_ms >= 250 or priority <= PRIORITY_ADMIN:
                            self.logger.log_info(
                                "GROUP DISPATCH JOB "
                                f"chat_id={chat_id} kind={kind} "
                                f"priority={priority} ms={elapsed_ms:.1f}"
                            )
                if queue.empty():
                    return
        finally:
            if self._workers.get(chat_id) is asyncio.current_task():
                self._workers.pop(chat_id, None)
            if queue.empty():
                self._queues.pop(chat_id, None)
                self._normal_pending.pop(chat_id, None)

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

    def reset_for_tests(self):
        self._queues.clear()
        self._workers.clear()
        self._normal_pending.clear()
        self._seq = 0
        self._closed = False
        for key in self.stats:
            self.stats[key] = 0
