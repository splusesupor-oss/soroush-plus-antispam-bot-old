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

try:
    from modules.group_id import normalize_group_id
    _HAS_NORMALIZE = True
except ImportError:
    _HAS_NORMALIZE = False
    def normalize_group_id(v):
        try:
            return str(int(v))
        except Exception:
            return str(v)

def _chat_key(chat_id):
    """Return a hashable key for chat_id. Never use InputPeer directly as dict key."""
    if chat_id is None:
        return "0"
    # Try to get numeric peer id via attributes (InputPeerChannel etc.)
    # InputPeerChannel is unhashable, so we must extract its id.
    for attr in ("channel_id", "chat_id", "user_id", "id"):
        try:
            val = getattr(chat_id, attr, None)
            if isinstance(val, int):
                # Use normalize to handle -100... and channel offset consistently
                if _HAS_NORMALIZE:
                    return normalize_group_id(val)
                return str(val)
            if val is not None:
                # Try int conversion
                try:
                    ival = int(val)
                    if _HAS_NORMALIZE:
                        return normalize_group_id(ival)
                    return str(ival)
                except Exception:
                    return str(val)
        except Exception:
            continue
    # Try direct int conversion
    try:
        ival = int(chat_id)
        if _HAS_NORMALIZE:
            return normalize_group_id(ival)
        return str(ival)
    except Exception:
        pass
    # Fallback: try get_peer_id via utils if available
    try:
        from splusthon import utils as _sutils
        peer = _sutils.get_peer_id(chat_id)
        if peer is not None:
            try:
                return normalize_group_id(peer) if _HAS_NORMALIZE else str(int(peer))
            except Exception:
                return str(peer)
    except Exception:
        pass
    # Last resort: string representation (always hashable)
    try:
        return str(chat_id)
    except Exception:
        return "0"

def _key_for_dict(chat_id):
    # Alias for clarity
    return _chat_key(chat_id)

# Set while a GroupDispatcher worker is running its factory.
# Value is priority (0=admin, 1=command, 2=normal) or False when not in dispatch.
# The patched send_message/reply uses this to decide enqueue vs direct and to set send priority.
_DISPATCH_ACTIVE = contextvars.ContextVar("outgoing_dispatch_active", default=False)

# Each client gets its own OutgoingSender via client._outgoing_sender
_SENDER_ATTR = "_outgoing_sender"
_PATCHED_ATTR = "_outgoing_sender_patched"

# Per-chat gate for low-priority sends to prevent sender_pending explosion per group.
# Each chat has its own gate with limit 2, so 32+ groups do not share a global lock.
# High-priority (admin/moderation, priority 0) bypasses the gate.
class _LowGate:
    def __init__(self, limit=1):
        self.limit = int(limit)
        self.inflight = 0
        self._waiters = []
    async def acquire(self):
        import asyncio, time
        started = time.perf_counter()
        loop = asyncio.get_running_loop()
        while self.inflight >= self.limit:
            fut = loop.create_future()
            self._waiters.append(fut)
            try:
                await fut
            except asyncio.CancelledError:
                if fut in self._waiters:
                    self._waiters.remove(fut)
                raise
        self.inflight += 1
        return (time.perf_counter() - started) * 1000
    def release(self):
        if self.inflight > 0:
            self.inflight -= 1
        while self._waiters and self.inflight < self.limit:
            fut = self._waiters.pop(0)
            if not fut.done():
                fut.set_result(True)

# Per-chat gates: chat_key -> _LowGate, so no global lock between groups
_CHAT_GATES = {}
def _gate_for_chat(chat_id):
    key = _chat_key(chat_id)
    gate = _CHAT_GATES.get(key)
    if gate is None:
        gate = _LowGate(limit=2)
        _CHAT_GATES[key] = gate
    return gate


class OutgoingSender:
    """Per-chat queue for outgoing sends. Separate from delete queues."""

    def __init__(self, client, logger, *, max_per_chat=800):
        self.client = client
        self.logger = logger
        self.max_per_chat = int(max_per_chat)
        # Per-chat queues: separate for notification (priority 0, auto) vs normal (priority 1)
        # This ensures a flood of normal replies does not delay an urgent auto notification,
        # and vice versa. Each has its own worker per chat.
        self._queues = {}  # (chat_key, kind) -> PriorityQueue where kind is "notif" or "normal"
        self._workers = {}  # (chat_key, kind) -> Task
        self._seq = 0
        self._closed = False
        self.stats = {"enqueued": 0, "sent": 0, "failed": 0, "dropped": 0}

    def _queue_key(self, chat_id, priority):
        kind = "notif" if int(priority) == 0 else "normal"
        return (_chat_key(chat_id), kind)

    def _queue_for(self, chat_id, priority=1):
        key = self._queue_key(chat_id, priority)
        q = self._queues.get(key)
        if q is None:
            q = asyncio.PriorityQueue()
            self._queues[key] = q
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
        qkey = self._queue_key(chat_id, pri)
        q = self._queue_for(chat_id, pri)
        if q.qsize() >= self.max_per_chat:
            self.stats["dropped"] += 1
            if self.logger:
                self.logger.log_info(f"OUTGOING SEND DROP chat_id={chat_id} qsize={q.qsize()} kind={'notif' if pri==0 else 'normal'}")
            return False
        self._seq += 1
        q.put_nowait((pri, self._seq, chat_id, coro_factory, on_done, time.perf_counter()))
        self.stats["enqueued"] += 1
        worker = self._workers.get(qkey)
        if worker is None or worker.done():
            self._workers[qkey] = asyncio.create_task(self._worker(qkey, chat_id, q))
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

    async def _worker(self, qkey, chat_id, queue):
        key = qkey
        if self.logger:
            self.logger.log_info(f"OUTGOING SEND WORKER START chat_id={chat_id} key={key} kind={'notif' if 'notif' in str(key) else 'normal'}")
        try:
            while True:
                try:
                    item = await queue.get()
                    # Support both old (5-tuple) and new (6-tuple with chat_id) formats
                    if len(item) == 6:
                        priority, seq, orig_chat_id, factory, on_done, enqueued_at = item
                        # Use orig_chat_id for logging if different from worker's chat_id
                        if orig_chat_id is not None:
                            chat_id = orig_chat_id
                    else:
                        priority, seq, factory, on_done, enqueued_at = item
                except asyncio.CancelledError:
                    raise
                queue_wait_ms = (time.perf_counter() - enqueued_at) * 1000
                if queue_wait_ms >= 50 and self.logger:
                    self.logger.log_info(f"OUTGOING SEND QUEUE_WAIT chat_id={chat_id} queue_wait_ms={queue_wait_ms:.1f} priority={priority}")
                started = time.perf_counter()
                result = None
                _is_low = int(priority) >= 1
                gate_wait_ms = 0
                _gate = _gate_for_chat(chat_id) if _is_low else None
                if _is_low:
                    gate_wait_ms = await _gate.acquire()
                    if gate_wait_ms >= 20 and self.logger:
                        self.logger.log_info(f"OUTGOING SEND GATE wait_ms={gate_wait_ms:.1f} chat_id={chat_id} priority={priority}")
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
                    if _is_low:
                        _gate.release()
                    queue.task_done()
                    if self.logger:
                        elapsed = (time.perf_counter() - started) * 1000
                        if elapsed >= 200:
                            self.logger.log_info(f"OUTGOING SEND TIME chat_id={chat_id} priority={priority} send_ms={elapsed:.1f} gate_wait_ms={gate_wait_ms:.1f}")
                if queue.empty():
                    await asyncio.sleep(0)
                    if queue.empty():
                        return
        finally:
            if self._workers.get(qkey) is asyncio.current_task():
                self._workers.pop(qkey, None)
            if queue.empty():
                self._queues.pop(qkey, None)

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
        dispatch_prio = _DISPATCH_ACTIVE.get()
        # dispatch_prio is False when not in dispatch, or 0/1/2 when in dispatch
        if dispatch_prio is not False and dispatch_prio is not None:
            # Inside GroupDispatcher: enqueue and return immediately
            chat_id = kwargs.get("entity") or kwargs.get("chat_id")
            if chat_id is None and args:
                first = args[0]
                if isinstance(first, int):
                    chat_id = first
                else:
                    chat_id = getattr(first, "id", first)
            # Map dispatch priority to send priority: admin(0)->0, command(1)->0, normal(2)->1
            # So command/moderation replies are highest priority
            if isinstance(dispatch_prio, int):
                if dispatch_prio <= 1:  # admin or command
                    default_prio = 0
                else:
                    default_prio = 1
            else:
                default_prio = 1
            priority = kwargs.pop("priority", default_prio)
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
        dispatch_prio = _DISPATCH_ACTIVE.get()
        if dispatch_prio is not False and dispatch_prio is not None:
            chat_id = getattr(event, "chat_id", None)
            if isinstance(dispatch_prio, int):
                if dispatch_prio <= 1:
                    default_prio = 0
                else:
                    default_prio = 1
            else:
                default_prio = 1
            priority = kwargs.pop("priority", default_prio)
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

def _wrap_call_with_gate(client, logger):
    orig = getattr(client, "_call", None)
    if orig is None or getattr(orig, "_patched_gate", False):
        return False
    import functools
    # Define request priorities
    _LOW = {"SendMessageRequest", "SendMediaRequest", "SendMultiMediaRequest", "ForwardMessagesRequest", "SendInlineBotResultRequest"}
    _HIGH = {"DeleteMessagesRequest", "EditBannedRequest", "EditAdminRequest", "EditChatDefaultBannedRightsRequest", "DeleteChatUserRequest"}
    _HEAVY = {"GetHistoryRequest", "GetMessagesRequest", "GetChannelDifferenceRequest", "GetDifferenceRequest", "GetParticipantsRequest"}
    def _req_name(req):
        try:
            # Unwrap InvokeWithoutUpdates etc.
            cur = req
            seen = set()
            while cur is not None and id(cur) not in seen:
                seen.add(id(cur))
                inner = getattr(cur, "query", None)
                if inner is None:
                    break
                cur = inner
            return type(cur).__name__
        except Exception:
            return type(req).__name__
    @functools.wraps(orig)
    async def wrapped(sender, request, ordered=False, flood_sleep_threshold=None):
        name = _req_name(request)
        is_low = name in _LOW
        is_high = name in _HIGH
        # Only gate low-priority per-chat; high bypasses
        gate_wait = 0
        _gate = None
        # For low-priority, we need chat_id to get per-chat gate. Try to extract from request.
        if is_low:
            try:
                # Try to get chat_id from request for per-chat gate
                _chat_for_gate = None
                for attr in ("peer", "channel", "entity", "chat_id"):
                    val = getattr(request, attr, None)
                    if val is not None:
                        for nested in ("channel_id", "chat_id", "user_id", "id"):
                            v2 = getattr(val, nested, None)
                            if v2 is not None:
                                _chat_for_gate = v2
                                break
                        if _chat_for_gate is not None:
                            break
                        if isinstance(val, int):
                            _chat_for_gate = val
                            break
                if _chat_for_gate is None:
                    _chat_for_gate = "global"
                _gate = _gate_for_chat(_chat_for_gate)
                gate_wait = await _gate.acquire()
            except Exception:
                gate_wait = 0
                _gate = None
            if gate_wait >= 20 and logger:
                # Find inflight for logging
                try:
                    infl = _gate.inflight if _gate else 0
                except Exception:
                    infl = 0
                logger.log_info(f"OUTGOING RPC GATE request={name} wait_ms={gate_wait:.1f} inflight_low={infl}")
        try:
            return await orig(sender, request, ordered=ordered, flood_sleep_threshold=flood_sleep_threshold)
        finally:
            if is_low and _gate is not None:
                try:
                    _gate.release()
                except Exception:
                    pass
    wrapped._patched_gate = True
    try:
        client._call = wrapped
        return True
    except Exception:
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
    _wrap_call_with_gate(client, logger)
    # Also store bot reference for event patching
    try:
        client._outgoing_sender_bot = bot
    except Exception:
        pass
    if logger:
        logger.log_info("OUTGOING SENDER installed (per-chat, separate from delete queue) + _call gate")
    return sender

def dispatch_active():
    return bool(_DISPATCH_ACTIVE.get())

def set_dispatch_active(active: bool):
    return _DISPATCH_ACTIVE.set(bool(active))

# For GroupDispatcher to use
DISPATCH_ACTIVE_VAR = _DISPATCH_ACTIVE
