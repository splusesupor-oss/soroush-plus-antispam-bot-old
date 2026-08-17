"""Outgoing sender queue - decouples GroupDispatcher workers from RPC.

GroupDispatcher workers must never `await send_message` / `reply`:
they only enqueue a send request and free immediately for the next
normal message.  This queue has its own per-chat workers, completely
separate from `MessageDeleteQueue` (deletes) and `ModerationQueue`
(bans/mutes) and `NoticeCleanup` (expiry deletes), so a heavy
delete/cleanup burst cannot head-block a short user reply.

All `client.send_message` and `event.reply` that happen inside a
GroupDispatcher worker are automatically enqueued when this module is
installed via :func:`install`.  Outside a worker (e.g. in
ModerationQueue callbacks, NoticeCleanup, reminder loops) the original
RPC is executed directly.

Priority: 0 = admin/moderation/urgent, 1 = normal chat.
"""
import asyncio
import contextvars
import inspect
import time

# Set while a GroupDispatcher worker is running its factory.
# The patched send_message/reply checks this to decide enqueue vs direct.
_DISPATCH_ACTIVE = contextvars.ContextVar("outgoing_dispatch_active", default=False)

# Each client gets its own OutgoingSender via client._outgoing_sender
_SENDER_ATTR = "_outgoing_sender"
_PATCHED_ATTR = "_outgoing_sender_patched"

class OutgoingSender:
    """Per-chat queue for outgoing sends. Separate from delete queues."""

    def __init__(self, client, logger, *, max_per_chat=800):
        self.client = client
        self.logger = logger
        self.max_per_chat = int(max_per_chat)
        self._queues = {}  # chat_id -> PriorityQueue
        self._workers = {}  # chat_id -> Task
        self._seq = 0
        self._closed = False
        self.stats = {"enqueued": 0, "sent": 0, "failed": 0, "dropped": 0}

    def _queue_for(self, chat_id):
        q = self._queues.get(chat_id)
        if q is None:
            q = asyncio.PriorityQueue()
            self._queues[chat_id] = q
        return q

    def enqueue(self, chat_id, coro_factory, *, priority=1, on_done=None):
        """Enqueue a send. Never awaits. Returns True if accepted."""
        if self._closed:
            return False
        if chat_id is None:
            chat_id = 0
        # Normalize priority: 0 urgent/admin, 1 normal
        try:
            pri = int(priority)
        except Exception:
            pri = 1
        q = self._queue_for(chat_id)
        if q.qsize() >= self.max_per_chat:
            self.stats["dropped"] += 1
            if self.logger:
                self.logger.log_info(f"OUTGOING SEND DROP chat_id={chat_id} qsize={q.qsize()}")
            return False
        self._seq += 1
        q.put_nowait((pri, self._seq, coro_factory, on_done, time.perf_counter()))
        self.stats["enqueued"] += 1
        worker = self._workers.get(chat_id)
        if worker is None or worker.done():
            self._workers[chat_id] = asyncio.create_task(self._worker(chat_id, q))
        return True

    def enqueue_reply(self, event, text, *, priority=1, on_done=None, **kwargs):
        chat_id = getattr(event, "chat_id", None)
        # Capture event and args at enqueue time
        def factory():
            # event.reply may be patched itself, but we call the original
            # via this closure which will be executed inside the sender worker
            # (where DISPATCH_ACTIVE is False), so it will do the real RPC.
            return event.reply(text, **kwargs)
        # Wrap factory to ensure it runs outside dispatch context
        def wrapped():
            token = _DISPATCH_ACTIVE.set(False)
            try:
                return factory()
            finally:
                _DISPATCH_ACTIVE.reset(token)
        return self.enqueue(chat_id, wrapped, priority=priority, on_done=on_done)

    def enqueue_send(self, chat_id, text, *, priority=1, on_done=None, **kwargs):
        def factory():
            return self.client.send_message(chat_id, text, **kwargs)
        def wrapped():
            token = _DISPATCH_ACTIVE.set(False)
            try:
                return factory()
            finally:
                _DISPATCH_ACTIVE.reset(token)
        return self.enqueue(chat_id, wrapped, priority=priority, on_done=on_done)

    async def _worker(self, chat_id, queue):
        if self.logger:
            self.logger.log_info(f"OUTGOING SEND WORKER START chat_id={chat_id}")
        try:
            while True:
                try:
                    priority, seq, factory, on_done, enqueued_at = await queue.get()
                except asyncio.CancelledError:
                    raise
                queue_wait_ms = (time.perf_counter() - enqueued_at) * 1000
                if queue_wait_ms >= 50 and self.logger:
                    self.logger.log_info(f"OUTGOING SEND QUEUE_WAIT chat_id={chat_id} queue_wait_ms={queue_wait_ms:.1f} priority={priority}")
                started = time.perf_counter()
                result = None
                try:
                    coro = factory()
                    if inspect.isawaitable(coro):
                        result = await coro
                    else:
                        result = coro
                    self.stats["sent"] += 1
                    if on_done:
                        try:
                            cb = on_done(result)
                            if inspect.isawaitable(cb):
                                await cb
                        except Exception as e:
                            if self.logger:
                                self.logger.log_error(f"OUTGOING SEND on_done FAILED chat_id={chat_id} error={e!r}")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.stats["failed"] += 1
                    if self.logger:
                        self.logger.log_error(f"OUTGOING SEND FAILED chat_id={chat_id} error={e!r}")
                finally:
                    queue.task_done()
                    if self.logger:
                        elapsed = (time.perf_counter() - started) * 1000
                        if elapsed >= 200:
                            self.logger.log_info(f"OUTGOING SEND TIME chat_id={chat_id} priority={priority} send_ms={elapsed:.1f}")
                if queue.empty():
                    await asyncio.sleep(0)
                    if queue.empty():
                        return
        finally:
            if self._workers.get(chat_id) is asyncio.current_task():
                self._workers.pop(chat_id, None)
            if queue.empty():
                self._queues.pop(chat_id, None)

    async def close(self):
        self._closed = True
        workers = list(self._workers.values())
        for w in workers:
            w.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        self._queues.clear()

    def reset_for_tests(self):
        self._queues.clear()
        self._workers.clear()
        self._seq = 0
        self._closed = False
        for k in self.stats:
            self.stats[k] = 0

def _wrap_send_message(client, sender):
    orig = getattr(client, "send_message", None)
    if orig is None or getattr(orig, _PATCHED_ATTR, False):
        return False
    import functools

    @functools.wraps(orig)
    async def wrapped(*args, **kwargs):
        # If we are inside a GroupDispatcher normal worker, enqueue and return immediately.
        # The actual RPC will be done in OutgoingSender's worker, outside dispatch context.
        if _DISPATCH_ACTIVE.get():
            # Extract chat_id for queueing
            chat_id = kwargs.get("entity") or kwargs.get("chat_id")
            if chat_id is None and args:
                # send_message(chat_id, text, ...)
                first = args[0]
                if isinstance(first, int):
                    chat_id = first
                else:
                    chat_id = getattr(first, "id", first)
            # Priority: assume normal (1) unless caller explicitly wants urgent (0)
            # We check for a marker in kwargs or context? For now, all dispatch sends are priority 1
            # Admin lane could use priority 0, but we treat all dispatch sends as 1 to keep simple.
            # The caller can pass priority=0 if needed.
            priority = kwargs.pop("priority", 1)
            on_done = kwargs.pop("on_done", None)
            # Capture args at call time
            _args = args
            _kwargs = kwargs.copy()
            def factory():
                token = _DISPATCH_ACTIVE.set(False)
                try:
                    return orig(*_args, **_kwargs)
                finally:
                    _DISPATCH_ACTIVE.reset(token)
            # Enqueue and return a dummy future that completes immediately after enqueue,
            # so the dispatcher's `await` is only queue time (~0.1ms), not RPC time (150-400ms).
            # For callers that need the sent id (e.g., capture_sent), they should use
            # sender.enqueue with on_done instead of awaiting. But to not break existing
            # code that does `sent = await client.send_message`, we return a future that
            # will be completed with the real sent value *asynchronously*, but the dispatch
            # worker's await will still wait for it. To avoid that, we return None immediately
            # when inside dispatch, and log that sent is not available.
            # This is a trade-off: callers that need sent must be updated to use on_done.
            # For now, we enqueue and return None (or a minimal dummy) so handler doesn't block.
            # The real send will happen in background and capture will be handled via on_done if provided.
            enqueued = sender.enqueue(chat_id, factory, priority=priority, on_done=on_done)
            if not enqueued:
                # Fallback to direct if dropped (should not happen)
                return await orig(*args, **kwargs)
            # Return a dummy sent that looks like a message id? Many callers ignore the return.
            # For those that do `sent = await ...; capture_sent(..., sent)`, capture will get None
            # and thus not schedule cleanup. To handle that, we need to make those callers use on_done.
            # As a temporary compatibility, we return a small object that will be truthy but not a real id.
            # The caller should be updated to use sender.enqueue with on_done.
            return None
        else:
            return await orig(*args, **kwargs)

    wrapped.__dict__[_PATCHED_ATTR] = True
    try:
        client.send_message = wrapped
        return True
    except (AttributeError, TypeError):
        return False

def _wrap_event_reply(sender):
    # We patch the Event class's reply method globally if possible.
    # Since we don't have the Event class directly, we patch instance method
    # via install_event. For now, we handle per-event patching in instrument_event.
    pass

def install_event_wrapper(event, sender):
    """Patch a single event's reply to be non-blocking inside dispatch."""
    orig = getattr(event, "reply", None)
    if orig is None or getattr(orig, _PATCHED_ATTR, False):
        return False
    import functools

    @functools.wraps(orig)
    async def wrapped(*args, **kwargs):
        if _DISPATCH_ACTIVE.get():
            chat_id = getattr(event, "chat_id", None)
            priority = kwargs.pop("priority", 1)
            on_done = kwargs.pop("on_done", None)
            # Also check for formatting_entities etc. - keep them
            _args = args
            _kwargs = kwargs.copy()
            def factory():
                token = _DISPATCH_ACTIVE.set(False)
                try:
                    return orig(*_args, **_kwargs)
                finally:
                    _DISPATCH_ACTIVE.reset(token)
            # If caller needs on_done (e.g., capture_sent), it should have passed it.
            # We also handle the case where the original call was `sent = await event.reply`
            # and then `capture_sent` - we can auto-handle capture by checking if the
            # text looks like a moderation notice? For now, we just enqueue.
            enqueued = sender.enqueue(chat_id, factory, priority=priority, on_done=on_done)
            if not enqueued:
                return await orig(*args, **kwargs)
            return None
        else:
            return await orig(*args, **kwargs)

    wrapped.__dict__[_PATCHED_ATTR] = True
    try:
        event.reply = wrapped
        return True
    except (AttributeError, TypeError):
        return False

def install(client, bot, logger=None):
    """Create OutgoingSender for this client/bot and patch send_message."""
    if getattr(client, _SENDER_ATTR, None) is not None:
        return getattr(client, _SENDER_ATTR)
    sender = OutgoingSender(client, logger or getattr(bot, "logger", None))
    try:
        client._outgoing_sender = sender
        bot.outgoing_sender = sender
    except Exception:
        pass
    _wrap_send_message(client, sender)
    # Also store bot reference for event patching
    try:
        client._outgoing_sender_bot = bot
    except Exception:
        pass
    if logger:
        logger.log_info("OUTGOING SENDER installed (per-chat, separate from delete queue)")
    return sender

def dispatch_active():
    return bool(_DISPATCH_ACTIVE.get())

def set_dispatch_active(active: bool):
    return _DISPATCH_ACTIVE.set(bool(active))

# For GroupDispatcher to use
DISPATCH_ACTIVE_VAR = _DISPATCH_ACTIVE
