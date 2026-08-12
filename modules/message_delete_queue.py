"""Per-group asynchronous queue for automatic message deletions."""
import asyncio
import time


class MessageDeleteQueue:
    """Keep delete RPCs out of incoming-message handlers.

    Each chat has an independent FIFO worker.  A small global semaphore bounds
    simultaneous delete RPCs, while one chat's hundreds of IDs never become a
    synchronous loop in another chat's message handler.
    """
    def __init__(self, client, logger, *, batch_size=100, max_concurrent=2):
        self.client = client
        self.logger = logger
        self.batch_size = batch_size
        self._queues = {}
        self._workers = {}
        self._pending_ids = set()
        self._rpc_slots = asyncio.Semaphore(max_concurrent)

    def enqueue(self, chat_id, message_ids):
        """Schedule unique IDs and return a Future of ``(deleted, remaining)``."""
        ids = []
        for message_id in message_ids:
            if not isinstance(message_id, int) or message_id <= 0:
                continue
            key = (chat_id, message_id)
            if key in self._pending_ids:
                continue
            self._pending_ids.add(key)
            ids.append(message_id)
        loop = asyncio.get_running_loop()
        result = loop.create_future()
        if not ids:
            result.set_result((0, []))
            return result

        queue = self._queues.get(chat_id)
        if queue is None:
            queue = asyncio.Queue()
            self._queues[chat_id] = queue
        queue.put_nowait((ids, result))
        self.logger.log_info(
            "DELETE QUEUE SIZE "
            f"chat_id={chat_id} queued_ids={len(ids)} pending={queue.qsize()}"
        )
        worker = self._workers.get(chat_id)
        if worker is None or worker.done():
            self._workers[chat_id] = asyncio.create_task(
                self._worker(chat_id, queue)
            )
        return result

    async def _delete_ids(self, chat_id, ids):
        deleted = 0
        remaining = []
        for start in range(0, len(ids), self.batch_size):
            batch = ids[start:start + self.batch_size]
            self.logger.log_info(
                f"BATCH DELETE START chat_id={chat_id} count={len(batch)}"
            )
            succeeded = False
            for attempt in range(1, 4):
                started = time.perf_counter()
                try:
                    async with self._rpc_slots:
                        await self.client.delete_messages(chat_id, batch)
                    deleted += len(batch)
                    succeeded = True
                    self.logger.log_info(
                        "DELETE MESSAGE RPC TIME "
                        f"chat_id={chat_id} count={len(batch)} attempt={attempt} "
                        f"rpc_ms={(time.perf_counter() - started) * 1000:.2f}"
                    )
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self.logger.log_error(
                        "DELETE MESSAGE RPC FAILED "
                        f"chat_id={chat_id} count={len(batch)} attempt={attempt} "
                        f"error={error!r}"
                    )
                    if attempt < 3:
                        await asyncio.sleep(0.2 * attempt)
            if succeeded:
                self.logger.log_info(
                    f"BATCH DELETE FINISHED chat_id={chat_id} count={len(batch)}"
                )
                # Let command-response tasks run before this chat's next batch.
                await asyncio.sleep(0)
                continue

            # Isolate invalid/deleted IDs; successful individual deletions are
            # still counted precisely and failed ones remain visible.
            for message_id in batch:
                item_ok = False
                for attempt in range(1, 4):
                    started = time.perf_counter()
                    try:
                        async with self._rpc_slots:
                            await self.client.delete_messages(chat_id, [message_id])
                        deleted += 1
                        item_ok = True
                        self.logger.log_info(
                            "DELETE MESSAGE RPC TIME "
                            f"chat_id={chat_id} count=1 attempt={attempt} "
                            f"rpc_ms={(time.perf_counter() - started) * 1000:.2f}"
                        )
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        if attempt == 3:
                            self.logger.log_error(
                                "DELETE MESSAGE UNRESOLVED "
                                f"chat_id={chat_id} message_id={message_id} "
                                f"error={error!r}"
                            )
                        else:
                            await asyncio.sleep(0.2 * attempt)
                if not item_ok:
                    remaining.append(message_id)
        return deleted, remaining

    async def _worker(self, chat_id, queue):
        self.logger.log_info(f"DELETE TASK START chat_id={chat_id}")
        try:
            while True:
                ids, result = await queue.get()
                try:
                    deleted, remaining = await self._delete_ids(chat_id, ids)
                    if not result.done():
                        result.set_result((deleted, remaining))
                except asyncio.CancelledError:
                    if not result.done():
                        result.cancel()
                    raise
                except Exception as error:
                    self.logger.log_error(
                        f"DELETE TASK FAILED chat_id={chat_id} error={error!r}"
                    )
                    if not result.done():
                        result.set_result((0, ids))
                finally:
                    for message_id in ids:
                        self._pending_ids.discard((chat_id, message_id))
                    queue.task_done()
                if queue.empty():
                    return
        finally:
            if self._workers.get(chat_id) is asyncio.current_task():
                self._workers.pop(chat_id, None)
            if queue.empty():
                self._queues.pop(chat_id, None)
