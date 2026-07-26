"""صف اجرای RPCهای مدیریتی به‌ازای هر گروه.

فقط خود عملیات سنگین moderation در این صف قرار می‌گیرد. تصمیم‌گیری، بررسی
مجوز و تشخیص اسپم در handler انجام می‌شود و هر گروه worker مستقل خودش را دارد.
"""
import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass
class ModerationJob:
    action: str
    operation: Callable[[], Awaitable]
    enqueued_at: float
    on_success: Optional[Callable[[object], Awaitable]] = None
    on_failure: Optional[Callable[[BaseException], Awaitable]] = None


class ModerationQueue:
    """FIFO مستقل per-chat، بدون تأخیر یا retry مصنوعی."""

    def __init__(self, logger):
        self.logger = logger
        self._queues = {}
        self._workers = {}
        self._closed = False
        self._completed = 0
        self._queue_wait_total_ms = 0.0
        self._rpc_total_ms = 0.0

    def enqueue(self, chat_id, action, operation, *, on_success=None, on_failure=None):
        """عملیات را فوراً ثبت می‌کند و منتظر پایان RPC نمی‌ماند."""
        if self._closed:
            raise RuntimeError("moderation queue is closed")

        queue = self._queues.get(chat_id)
        if queue is None:
            queue = asyncio.Queue()
            self._queues[chat_id] = queue

        job = ModerationJob(
            action=action,
            operation=operation,
            enqueued_at=time.perf_counter(),
            on_success=on_success,
            on_failure=on_failure,
        )
        queue.put_nowait(job)
        self.logger.log_info(
            "MODERATION QUEUE ENQUEUED "
            f"chat_id={chat_id} action={action} pending={queue.qsize()}"
        )

        worker = self._workers.get(chat_id)
        if worker is None or worker.done():
            worker = asyncio.create_task(self._worker(chat_id, queue))
            self._workers[chat_id] = worker
        return job

    async def _worker(self, chat_id, queue):
        self.logger.log_info(f"MODERATION WORKER START chat_id={chat_id}")
        try:
            while True:
                job = await queue.get()
                started_at = time.perf_counter()
                queue_wait_ms = (started_at - job.enqueued_at) * 1000
                try:
                    result = await job.operation()
                    rpc_ms = (time.perf_counter() - started_at) * 1000
                    if result is False:
                        raise RuntimeError("moderation operation returned False")
                    self._record_completed(queue_wait_ms, rpc_ms)
                    self.logger.log_info(
                        "MODERATION RPC SUCCESS "
                        f"chat_id={chat_id} action={job.action} "
                        f"queue_wait_ms={queue_wait_ms:.2f} rpc_ms={rpc_ms:.2f} "
                        f"avg_queue_wait_ms={self._queue_wait_total_ms / self._completed:.2f} "
                        f"avg_rpc_ms={self._rpc_total_ms / self._completed:.2f}"
                    )
                    if job.on_success:
                        await self._run_callback(job.on_success, result, chat_id, job.action)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    rpc_ms = (time.perf_counter() - started_at) * 1000
                    self._record_completed(queue_wait_ms, rpc_ms)
                    self.logger.log_error(
                        "MODERATION RPC FAILED "
                        f"chat_id={chat_id} action={job.action} "
                        f"queue_wait_ms={queue_wait_ms:.2f} rpc_ms={rpc_ms:.2f} "
                        f"avg_queue_wait_ms={self._queue_wait_total_ms / self._completed:.2f} "
                        f"avg_rpc_ms={self._rpc_total_ms / self._completed:.2f} "
                        f"error={error!r}"
                    )
                    if job.on_failure:
                        await self._run_callback(job.on_failure, error, chat_id, job.action)
                finally:
                    queue.task_done()
                # بعد از آخرین کار worker را نگه نمی‌داریم؛ enqueue بعدی فوری worker
                # تازه می‌سازد و هیچ زمان‌بندی/خواب مصنوعی وارد مسیر نمی‌شود.
                if queue.empty():
                    return
        finally:
            if self._workers.get(chat_id) is asyncio.current_task():
                self._workers.pop(chat_id, None)
            if queue.empty():
                self._queues.pop(chat_id, None)

    def _record_completed(self, queue_wait_ms, rpc_ms):
        self._completed += 1
        self._queue_wait_total_ms += queue_wait_ms
        self._rpc_total_ms += rpc_ms

    async def _run_callback(self, callback, argument, chat_id, action):
        try:
            result = callback(argument)
            if inspect.isawaitable(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.logger.log_error(
                "MODERATION QUEUE CALLBACK FAILED "
                f"chat_id={chat_id} action={action} error={error!r}"
            )

    async def close(self):
        """برای shutdown تمیز؛ عملیات در حال اجرا را لغو می‌کند."""
        self._closed = True
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        self._queues.clear()
