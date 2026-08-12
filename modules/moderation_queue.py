"""صف FIFO عملیات moderation، با worker مستقل برای هر گروه."""
import asyncio
import inspect
import re
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


_DEFAULT_TIMEOUT_SECONDS = 20
_MAX_FLOOD_WAIT_RETRIES = 1


def flood_wait_seconds(error):
    """مدت FloodWait را بدون وابستگی مستقیم به نسخهٔ SPlusthon استخراج می‌کند."""
    name = error.__class__.__name__.lower()
    text = str(error)
    if "flood" not in name and "wait" not in name and "wait of" not in text.lower():
        return None
    for attribute in ("seconds", "value", "wait_seconds"):
        value = getattr(error, attribute, None)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    match = re.search(r"(?:wait of|wait)\s+(\d+(?:\.\d+)?)\s+seconds", text, re.I)
    return float(match.group(1)) if match else None


@dataclass
class ModerationJob:
    action: str
    user_id: object
    operation: Callable[[], Awaitable]
    enqueued_at: float
    timeout_seconds: float
    on_success: Optional[Callable[[object], Awaitable]] = None
    on_failure: Optional[Callable[[BaseException], Awaitable]] = None


class ModerationQueue:
    """یک moderation RPC هم‌زمان برای هر chat، بدون تأخیر مصنوعی."""

    def __init__(self, logger):
        self.logger = logger
        self._queues = {}
        self._workers = {}
        self._pending_keys = set()
        self._closed = False
        self._sequence = 0
        self._completed = 0
        self._queue_wait_total_ms = 0.0
        self._rpc_total_ms = 0.0

    def enqueue(
        self,
        chat_id,
        action,
        operation,
        *,
        user_id=None,
        timeout_seconds=_DEFAULT_TIMEOUT_SECONDS,
        on_success=None,
        on_failure=None,
    ):
        """job را فوری ثبت می‌کند؛ هرگز منتظر RPC نمی‌ماند.

        مقدار False یعنی همان action برای همان کاربر از قبل در صف یا در حال اجراست.
        """
        if self._closed:
            raise RuntimeError("moderation queue is closed")
        key = (chat_id, user_id, action)
        if key in self._pending_keys:
            self.logger.log_info(
                "MODERATION QUEUE DUPLICATE SKIPPED "
                f"chat_id={chat_id} action={action} user_id={user_id}"
            )
            return False

        queue = self._queues.get(chat_id)
        if queue is None:
            queue = asyncio.PriorityQueue()
            self._queues[chat_id] = queue
        self._pending_keys.add(key)
        job = ModerationJob(
            action=action,
            user_id=user_id,
            operation=operation,
            enqueued_at=time.perf_counter(),
            timeout_seconds=float(timeout_seconds),
            on_success=on_success,
            on_failure=on_failure,
        )
        # Punish/ban jobs must pass ordinary moderation work for this chat.
        priority = 0 if action in {"punish", "ban"} else 1
        self._sequence += 1
        queue.put_nowait((priority, self._sequence, job))
        self.logger.log_info(
            "MODERATION QUEUE ENQUEUED "
            f"chat_id={chat_id} action={action} user_id={user_id} pending={queue.qsize()}"
        )
        worker = self._workers.get(chat_id)
        if worker is None or worker.done():
            self._workers[chat_id] = asyncio.create_task(self._worker(chat_id, queue))
        return True

    async def _worker(self, chat_id, queue):
        self.logger.log_info(f"MODERATION WORKER START chat_id={chat_id}")
        try:
            while True:
                _priority, _sequence, job = await queue.get()
                rpc_started_at = time.perf_counter()
                queue_wait_ms = (rpc_started_at - job.enqueued_at) * 1000
                started_wall = time.time()
                result = "failed"
                error = None
                try:
                    self.logger.log_info(
                        "MODERATION RPC START "
                        f"chat_id={chat_id} action={job.action} user_id={job.user_id} "
                        f"queue_wait_ms={queue_wait_ms:.2f} rpc_started_at={started_wall:.3f}"
                    )
                    value = await self._run_job(chat_id, job)
                    if value is False:
                        raise RuntimeError("moderation operation returned False")
                    result = "success"
                    if job.on_success:
                        # Cleanup/notifications can involve slow delete/send
                        # RPCs. They must never hold this chat's punish worker.
                        asyncio.create_task(
                            self._run_callback(job.on_success, value, chat_id, job.action)
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as caught:
                    error = caught
                    if isinstance(caught, asyncio.TimeoutError):
                        result = "timeout"
                    else:
                        result = "failed"
                    if job.on_failure:
                        await self._run_callback(job.on_failure, caught, chat_id, job.action)
                    self.logger.log_error(
                        "MODERATION RPC FAILED "
                        f"chat_id={chat_id} action={job.action} user_id={job.user_id} "
                        f"error={caught!r}"
                    )
                finally:
                    finished_wall = time.time()
                    rpc_ms = (time.perf_counter() - rpc_started_at) * 1000
                    self._record_completed(queue_wait_ms, rpc_ms)
                    self.logger.log_info(
                        "MODERATION RPC FINISHED "
                        f"chat_id={chat_id} action={job.action} user_id={job.user_id} "
                        f"queue_wait_ms={queue_wait_ms:.2f} "
                        f"rpc_started_at={started_wall:.3f} rpc_finished_at={finished_wall:.3f} "
                        f"rpc_ms={rpc_ms:.2f} result={result} "
                        f"avg_queue_wait_ms={self._queue_wait_total_ms / self._completed:.2f} "
                        f"avg_rpc_ms={self._rpc_total_ms / self._completed:.2f}"
                    )
                    self._pending_keys.discard((chat_id, job.user_id, job.action))
                    queue.task_done()
                if queue.empty():
                    return
        finally:
            if self._workers.get(chat_id) is asyncio.current_task():
                self._workers.pop(chat_id, None)
            if queue.empty():
                self._queues.pop(chat_id, None)

    async def _run_job(self, chat_id, job):
        """deadline هر کوشش و تنها یک retry پس از FloodWait در همان worker."""
        for attempt in range(_MAX_FLOOD_WAIT_RETRIES + 1):
            try:
                # Ban/mute RPCs often contain entity resolution plus two
                # permission calls; the old 20s outer deadline cancelled a
                # still-running punishment and left only the warning.
                deadline = max(job.timeout_seconds, 45.0) if job.action in {"punish", "ban", "mute"} else job.timeout_seconds
                return await asyncio.wait_for(job.operation(), timeout=deadline)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                wait_seconds = flood_wait_seconds(error)
                if wait_seconds is None or attempt >= _MAX_FLOOD_WAIT_RETRIES:
                    raise
                self.logger.log_info(
                    "MODERATION FLOOD WAIT "
                    f"chat_id={chat_id} action={job.action} user_id={job.user_id} "
                    f"wait_seconds={wait_seconds:.2f} attempt={attempt + 1}"
                )
                # این sleep فقط worker همین گروه را متوقف می‌کند.
                await asyncio.sleep(wait_seconds)
        raise RuntimeError("unreachable moderation retry state")

    def _record_completed(self, queue_wait_ms, rpc_ms):
        self._completed += 1
        self._queue_wait_total_ms += queue_wait_ms
        self._rpc_total_ms += rpc_ms

    async def _run_callback(self, callback, argument, chat_id, action):
        try:
            result = callback(argument)
            if inspect.isawaitable(result):
                # callbackها نیز ممکن است پاسخ شبکه‌ای ارسال کنند؛ بی‌deadline نمی‌مانند.
                await asyncio.wait_for(result, timeout=10)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.logger.log_error(
                "MODERATION QUEUE CALLBACK FAILED "
                f"chat_id={chat_id} action={action} error={error!r}"
            )

    async def close(self):
        self._closed = True
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        self._queues.clear()
        self._pending_keys.clear()
