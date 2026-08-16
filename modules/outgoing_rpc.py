"""Isolation of outgoing RPCs on the single SPlusthon sender.

A slow ``send_message`` must not keep delete/ban/mute behind it, and a
``GetUsersRequest`` that already failed with 404/NOT_FOUND must not be
retried or re-enqueued.

This module does **not** change keepalive interval, flood retries of
transient 5xx/503, handler logic, or spam policy. It only:

* caps concurrent *low-priority* RPCs (notices / extra sends) on the shared sender
* short user-facing replies are ``urgent`` (text + context) and skip that cap
* the packer sends an urgent reply as its own packet and will not dump
  dozens of delete/notice RPCs onto the wire first
* delete/ban/mute stay ungated but sit behind urgent replies in the packer
* reconnect drops stuck LOW sends so they cannot block a new reply
* fail-fast + cache permanent GetUsers 404 so the same invalid id never
  re-enters ``_pending_state``
"""
import asyncio
import contextvars
import functools
import time


_PRIORITY = contextvars.ContextVar("outgoing_rpc_priority", default=None)
_CALL_MARKER = "_outgoing_rpc_call"
_CLIENT_MARKER = "_outgoing_rpc_installed"
_SENDER_MARKER = "_outgoing_rpc_sender"
_HIGH_OP_MARKER = "_outgoing_rpc_high_op"

URGENT = "urgent"
HIGH = "high"
LOW = "low"
NORMAL = "normal"
_URGENT_METHOD = "_outgoing_rpc_urgent_method"
_SEND_MARKER = "_outgoing_rpc_send"

# Content RPCs that pile up when the Soroush worker is sequential.
# Official Web/Desktop clients typically keep very few of these in flight;
# flooding them is the observed 3–8s rpc_wait with pending_rpc=4+.
_LOW_REQUESTS = {
    "SendMessageRequest",
    "SendMediaRequest",
    "SendMultiMediaRequest",
    "ForwardMessagesRequest",
    "SendInlineBotResultRequest",
}

# Moderation / delete must go onto the wire even while a send is waiting.
_HIGH_REQUESTS = {
    "DeleteMessagesRequest",
    "EditBannedRequest",
    "EditAdminRequest",
    "EditChatDefaultBannedRightsRequest",
    "DeleteChatUserRequest",
    "KickFromGroupCallRequest",
}

_PERMANENT_NAMES = {
    "NotFoundError",
    "BadRequestError",
    "PeerIdInvalidError",
    "UserIdInvalidError",
    "UsernameNotOccupiedError",
    "UsernameInvalidError",
    "ChannelInvalidError",
    "ChannelPrivateError",
    "InputUserDeactivatedError",
    "UserDeactivatedError",
    "UserDeactivatedBanError",
    "MessageIdInvalidError",
    "MessageAuthorRequiredError",
    "ChatAdminRequiredError",
    "ChatWriteForbiddenError",
    "UserNotParticipantError",
}

_PERMANENT_CODES = {400, 401, 403, 404}
_PERMANENT_MARKERS = (
    "NOT_FOUND",
    "PEER_ID_INVALID",
    "USER_ID_INVALID",
    "USERNAME_INVALID",
    "USERNAME_NOT_OCCUPIED",
    "CHANNEL_INVALID",
    "INPUT_USER_DEACTIVATED",
    "USER_DEACTIVATED",
    "MESSAGE_ID_INVALID",
)

_GET_USERS = "GetUsersRequest"
_LOW_INFLIGHT_LIMIT = 1
# Official clients keep a handful in flight. Packing 100 deletes into one
# container is what produces sender_pending=152 and a 1.3s+ rpc_wait on «هعی».
_MAX_SENDER_PENDING = 6
_NON_URGENT_BATCH = 2
_URGENT_WAIT_LOG_MS = 500
_CACHE_TTL_S = 15 * 60
_CACHE_MAX = 2000

_invalid_users = {}
_invalid_lock_generation = 0


class PermanentRpcError(Exception):
    """Cached permanent lookup failure; never sent again."""

    def __init__(self, message, *, code=404, request=None):
        super().__init__(message)
        self.code = code
        self.request = request


class _LowSlotGate:
    """At most ``limit`` low-priority ``_call``s in flight at once."""

    def __init__(self, limit=_LOW_INFLIGHT_LIMIT):
        self.limit = int(limit)
        self.inflight = 0
        self._waiters = []

    async def acquire(self):
        started = time.perf_counter()
        loop = asyncio.get_running_loop()
        while self.inflight >= self.limit:
            future = loop.create_future()
            self._waiters.append(future)
            try:
                await future
            except asyncio.CancelledError:
                if future in self._waiters:
                    self._waiters.remove(future)
                raise
        self.inflight += 1
        return (time.perf_counter() - started) * 1000

    def release(self):
        if self.inflight > 0:
            self.inflight -= 1
        while self._waiters and self.inflight < self.limit:
            future = self._waiters.pop(0)
            if not future.done():
                future.set_result(True)


def _now():
    return time.monotonic()


def unwrap_request(request):
    """Peel InvokeWithoutUpdates / InvokeAfterMsg wrappers."""
    seen = set()
    current = request
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        inner = getattr(current, "query", None)
        if inner is None:
            return current
        current = inner
    return request


def request_name(request):
    return type(unwrap_request(request)).__name__


def current_priority():
    return _PRIORITY.get()


def urgent_rpc():
    """Mark this task's RPCs as user-facing replies (bypass the heavy gate)."""
    return _UrgentScope()


class _UrgentScope:
    def __init__(self):
        self._token = None

    def __enter__(self):
        self._token = _PRIORITY.set(URGENT)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._token is not None:
            _PRIORITY.reset(self._token)
        return False


def request_message_text(request):
    """Plain text of a SendMessage-like request, if any."""
    payload = unwrap_request(request)
    for attr in ("message", "caption"):
        value = getattr(payload, attr, None)
        if isinstance(value, str):
            return value
        inner = getattr(value, "message", None)
        if isinstance(inner, str):
            return inner
    return ""


def request_priority(request):
    override = _PRIORITY.get()
    if override in {URGENT, HIGH, LOW, NORMAL}:
        return override
    name = request_name(request)
    if name in _HIGH_REQUESTS:
        return HIGH
    if name in _LOW_REQUESTS:
        if _looks_like_urgent_send(request):
            return URGENT
        return LOW
    return NORMAL


def _looks_like_urgent_send(request):
    try:
        from modules.urgent_send import is_urgent_text
    except Exception:
        return False
    return is_urgent_text(request_message_text(request))


def _state_rank(state):
    request = getattr(state, "request", None)
    name = request_name(request) if request is not None else ""
    if name in {"MsgsAck", "PingRequest", "MsgsStateInfo", "HttpWaitRequest"}:
        return 3
    priority = request_priority(request)
    if priority == URGENT:
        return 0
    if priority == HIGH:
        return 1
    return 2


def is_high_state(state):
    return _state_rank(state) <= 1


def _insert_ranked(deque, state, ranks=None):
    rank = _state_rank(state)
    if ranks is not None:
        ranks[id(state)] = rank
    if deque is None or rank >= 2:
        return False
    items = list(deque)
    pos = 0
    for index, existing in enumerate(items):
        if ranks is not None and id(existing) in ranks:
            existing_rank = ranks[id(existing)]
        else:
            existing_rank = _state_rank(existing)
        if existing_rank <= rank:
            pos = index + 1
        else:
            break
    items.insert(pos, state)
    deque.clear()
    deque.extend(items)
    if ranks is not None:
        live = {id(item) for item in items}
        for key in list(ranks):
            if key not in live:
                ranks.pop(key, None)
    return True


def _mark_one_urgent(owner, name):
    original = getattr(owner, name, None)
    if original is None or getattr(original, _URGENT_METHOD, False):
        return False

    async def hooked(*args, **kwargs):
        token = _PRIORITY.set(URGENT)
        try:
            return await original(*args, **kwargs)
        finally:
            _PRIORITY.reset(token)

    if not asyncio.iscoroutinefunction(original):
        def sync_hooked(*args, **kwargs):
            token = _PRIORITY.set(URGENT)
            try:
                return original(*args, **kwargs)
            finally:
                _PRIORITY.reset(token)
        setattr(sync_hooked, _URGENT_METHOD, True)
        try:
            setattr(owner, name, sync_hooked)
            return True
        except (AttributeError, TypeError):
            return False

    setattr(hooked, _URGENT_METHOD, True)
    try:
        setattr(owner, name, hooked)
        return True
    except (AttributeError, TypeError):
        return False


def mark_method_urgent(owner, name):
    """Wrap reply/respond so the send bypasses the heavy outgoing gate.

    SPlusthon ``NewMessage.Event`` stores ``reply`` on ``event.message``
    (``__getattr__`` / ``__setattr__`` after ``_init``). Mark both.
    """
    marked = _mark_one_urgent(owner, name)
    message = getattr(owner, "message", None)
    if message is not None and message is not owner:
        marked = _mark_one_urgent(message, name) or marked
    return marked


def get_users_ids(request):
    request = unwrap_request(request)
    if type(request).__name__ != _GET_USERS:
        return ()
    items = getattr(request, "id", None)
    if items is None:
        items = getattr(request, "users", None)
    if not items:
        return ()
    ids = []
    try:
        iterator = list(items)
    except TypeError:
        iterator = [items]
    for item in iterator:
        if isinstance(item, int):
            ids.append(item)
            continue
        for attr in ("user_id", "id"):
            value = getattr(item, attr, None)
            if value is not None:
                try:
                    ids.append(int(value))
                except (TypeError, ValueError):
                    pass
                break
    return tuple(ids)


def is_permanent_rpc_error(error):
    """True for 404/NOT_FOUND/invalid-peer — retrying cannot succeed."""
    if error is None:
        return False
    if isinstance(error, PermanentRpcError):
        return True
    name = type(error).__name__
    if name in _PERMANENT_NAMES:
        return True
    code = getattr(error, "code", None)
    try:
        if code is not None and abs(int(code)) in _PERMANENT_CODES:
            # 400/404 are client/permanent; 401/403 will not heal by retry.
            return True
    except (TypeError, ValueError):
        pass
    text = str(error).upper()
    return any(marker in text for marker in _PERMANENT_MARKERS)


def remember_invalid_users(request, error=None):
    ids = get_users_ids(request)
    if not ids:
        return ids
    expires = _now() + _CACHE_TTL_S
    payload = {"error": error, "expires": expires}
    if len(_invalid_users) >= _CACHE_MAX:
        oldest = sorted(_invalid_users, key=lambda key: _invalid_users[key]["expires"])
        for key in oldest[: max(1, _CACHE_MAX // 10)]:
            _invalid_users.pop(key, None)
    for user_id in ids:
        _invalid_users[user_id] = payload
    return ids


def cached_invalid_users(request):
    _prune_invalid_users()
    ids = get_users_ids(request)
    if not ids:
        return ()
    return tuple(user_id for user_id in ids if user_id in _invalid_users)


def _prune_invalid_users():
    now = _now()
    dead = [key for key, row in _invalid_users.items() if row["expires"] <= now]
    for key in dead:
        _invalid_users.pop(key, None)


def clear_invalid_user_cache():
    _invalid_users.clear()


def drop_stale_low_pending(sender, logger=None):
    """Fail stuck LOW sends on reconnect so they cannot block a new reply.

    SPlusthon ``_reconnect`` re-extends ``_pending_state`` onto the packer.
    A 15–23s notice sitting there would otherwise go back on the wire
    ahead of the next «سلام».
    """
    pending = getattr(sender, "_pending_state", None)
    if not pending:
        return 0
    removed = 0
    for msg_id, state in list(pending.items()):
        request = getattr(state, "request", None)
        if request_priority(request) != LOW:
            continue
        pending.pop(msg_id, None)
        future = getattr(state, "future", None)
        if future is not None and not future.done():
            future.set_exception(ConnectionError(
                "low-priority send dropped on reconnect"
            ))
        removed += 1
    if removed and logger is not None:
        logger.log_info(
            f"OUTGOING RPC DROP pending low send count={removed} "
            "reason=reconnect"
        )
    return removed


def drop_invalid_pending(sender, logger=None):
    """Remove cached-404 GetUsersRequest so reconnect cannot re-send them."""
    pending = getattr(sender, "_pending_state", None)
    if not pending:
        return 0
    removed = 0
    for msg_id, state in list(pending.items()):
        request = getattr(state, "request", None)
        if not cached_invalid_users(request):
            continue
        pending.pop(msg_id, None)
        future = getattr(state, "future", None)
        if future is not None and not future.done():
            future.set_exception(PermanentRpcError(
                "GetUsersRequest dropped: user already 404 NOT_FOUND",
                request=request,
            ))
        removed += 1
    if removed and logger is not None:
        logger.log_info(
            f"OUTGOING RPC DROP pending GetUsersRequest count={removed} "
            "reason=404_cached"
        )
    return removed


def _gate_for(client):
    gate = getattr(client, "_outgoing_low_gate", None)
    if gate is None:
        gate = _LowSlotGate(_LOW_INFLIGHT_LIMIT)
        try:
            client._outgoing_low_gate = gate
        except (AttributeError, TypeError):
            return _LowSlotGate(_LOW_INFLIGHT_LIMIT)
    return gate


def _log(logger, message):
    if logger is not None:
        logger.log_info(message)


def _sender_pending_count(sender):
    pending = getattr(sender, "_pending_state", None) if sender is not None else None
    if pending is None:
        return 0
    try:
        return len(pending)
    except TypeError:
        return 0


def _route_type(state, urgent):
    request = getattr(state, "request", None)
    name = request_name(request) if request is not None else ""
    if urgent or (name in _LOW_REQUESTS and _looks_like_urgent_send(request)):
        return "reply"
    if "Delete" in name:
        return "delete"
    if name in _HIGH_REQUESTS:
        return "moderation"
    if name in _LOW_REQUESTS:
        return "send"
    return "other"


def _sender_route_line(*, route_type, urgent, sender_pending, queue_wait_ms, cut_ahead):
    return (
        "SENDER ROUTE "
        f"type={route_type} "
        f"urgent={bool(urgent)} "
        f"sender_pending={int(sender_pending)} "
        f"queue_wait_ms={float(queue_wait_ms):.1f} "
        f"cut_ahead={bool(cut_ahead)}"
    )


def _wait_reason(urgent, sender_pending, parked, queue_wait_ms):
    if not urgent:
        return "non_urgent"
    if sender_pending >= _MAX_SENDER_PENDING:
        return "sender_pending_full"
    if parked:
        return "cut_ahead_behind_previous_batch"
    if queue_wait_ms >= _URGENT_WAIT_LOG_MS:
        return "send_loop_busy"
    return "ok"


def _wrap_call(client, logger):
    original = getattr(client, "_call", None)
    if original is None or getattr(original, _CALL_MARKER, False):
        return False

    async def _call(sender, request, ordered=False, flood_sleep_threshold=None):
        cached = cached_invalid_users(request)
        if cached:
            _log(
                logger,
                "OUTGOING RPC DROP request=GetUsersRequest "
                f"reason=404_cached user_ids={','.join(str(i) for i in cached)}",
            )
            raise PermanentRpcError(
                f"GetUsersRequest skipped; users {cached} already 404 NOT_FOUND",
                request=request,
            )

        priority = request_priority(request)
        gate = _gate_for(client)
        wait_ms = 0.0
        held = False
        started = time.perf_counter()
        pending_at_start = _sender_pending_count(sender)
        route_type = "reply" if priority == URGENT else (
            "delete" if "Delete" in request_name(request) else
            "moderation" if request_name(request) in _HIGH_REQUESTS else
            "send" if request_name(request) in _LOW_REQUESTS else "other"
        )
        if priority == URGENT and gate.inflight > 0:
            _log(
                logger,
                "URGENT SEND bypass=gate "
                f"request={request_name(request)} "
                f"inflight_low={gate.inflight}",
            )
        if priority == LOW:
            wait_ms = await gate.acquire()
            held = True
            if wait_ms >= 20:
                _log(
                    logger,
                    "OUTGOING RPC GATE "
                    f"request={request_name(request)} wait_ms={wait_ms:.1f} "
                    f"inflight_low={gate.inflight}",
                )
        try:
            return await original(
                sender,
                request,
                ordered=ordered,
                flood_sleep_threshold=flood_sleep_threshold,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if is_permanent_rpc_error(error) and get_users_ids(request):
                ids = remember_invalid_users(request, error)
                _log(
                    logger,
                    "OUTGOING RPC PERMANENT "
                    f"request=GetUsersRequest code={getattr(error, 'code', 404)} "
                    f"user_ids={','.join(str(i) for i in ids)} "
                    f"error={type(error).__name__}",
                )
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            if priority == URGENT and elapsed_ms >= _URGENT_WAIT_LOG_MS:
                _log(
                    logger,
                    "SENDER ROUTE WAIT "
                    f"type={route_type} urgent=True "
                    f"sender_pending={pending_at_start} "
                    f"queue_wait_ms={elapsed_ms:.1f} "
                    f"reason=rpc_or_queue_wait "
                    f"gate_wait_ms={wait_ms:.1f}",
                )
            if held:
                gate.release()

    setattr(_call, _CALL_MARKER, True)
    try:
        client._call = _call
        return True
    except (AttributeError, TypeError):
        return False


def _wrap_high_operation(client, name):
    original = getattr(client, name, None)
    if original is None or getattr(original, _HIGH_OP_MARKER, False):
        return False

    @functools.wraps(original)
    async def hooked(*args, **kwargs):
        token = _PRIORITY.set(HIGH)
        try:
            return await original(*args, **kwargs)
        finally:
            _PRIORITY.reset(token)

    setattr(hooked, _HIGH_OP_MARKER, True)
    try:
        setattr(client, name, hooked)
        return True
    except (AttributeError, TypeError):
        return False


class _WatchedPending(dict):
    """``_pending_state`` that wakes the packer when in-flight RPCs finish."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.changed = asyncio.Event()

    def _notify(self):
        self.changed.set()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._notify()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._notify()

    def pop(self, key, *args):
        result = super().pop(key, *args)
        self._notify()
        return result

    def clear(self):
        super().clear()
        self._notify()


def _watch_pending(sender):
    pending = getattr(sender, "_pending_state", None)
    if isinstance(pending, _WatchedPending):
        return pending
    watched = _WatchedPending()
    if pending:
        try:
            watched.update(pending)
        except Exception:
            pass
    try:
        sender._pending_state = watched
    except (AttributeError, TypeError):
        return pending
    return watched


class _PrioritySendQueue:
    """Proxy in front of SPlusthon ``MessagePacker``.

    ``MessagePacker`` uses ``__slots__``, so ``packer.append = ...`` raises
    ``AttributeError: ... attribute 'append' is read-only``. Replace the
    sender's queue object instead of mutating packer methods.

    ``get`` sends an urgent reply as its own packet and will not push more
    non-urgent RPCs onto the wire while ``sender_pending`` is already high.
    """

    def __init__(self, inner, pending=None, logger=None):
        self._inner = inner
        self._ranks = {}
        self._enqueued_at = {}
        self._pending = pending
        self._logger = logger

    def _rank_of(self, state):
        stored = self._ranks.get(id(state))
        if stored is not None:
            return stored
        return _state_rank(state)

    def _pending_count(self):
        pending = self._pending
        if pending is None:
            return 0
        try:
            return len(pending)
        except TypeError:
            return 0

    def _wake_waiters(self):
        pending = self._pending
        changed = getattr(pending, "changed", None)
        if changed is not None:
            changed.set()

    def _mark_enqueued(self, state):
        self._enqueued_at[id(state)] = time.perf_counter()

    def append(self, state):
        inner = self._inner
        deque = getattr(inner, "_deque", None)
        ready = getattr(inner, "_ready", None)
        self._mark_enqueued(state)
        if _insert_ranked(deque, state, self._ranks):
            if ready is not None:
                ready.set()
            if self._ranks.get(id(state)) == 0:
                self._wake_waiters()
            return None
        self._ranks[id(state)] = _state_rank(state)
        return inner.append(state)

    def extend(self, states):
        inner = self._inner
        deque = getattr(inner, "_deque", None)
        ready = getattr(inner, "_ready", None)
        rest = []
        inserted = False
        woke_urgent = False
        for row in states:
            self._mark_enqueued(row)
            if _insert_ranked(deque, row, self._ranks):
                inserted = True
                if self._ranks.get(id(row)) == 0:
                    woke_urgent = True
            else:
                self._ranks[id(row)] = _state_rank(row)
                rest.append(row)
        if inserted and ready is not None:
            ready.set()
        if woke_urgent:
            self._wake_waiters()
        if rest:
            return inner.extend(rest)
        if inserted:
            return None
        return inner.extend(list(states))

    async def get(self):
        """Pack the next outgoing batch.

        Urgent replies are packed alone so they are not buried in a
        100-item delete/notice container. Non-urgent traffic waits when
        ``sender_pending`` is already at the cap.
        """
        inner = self._inner
        original = getattr(inner, "get", None)
        deque = getattr(inner, "_deque", None)
        ready = getattr(inner, "_ready", None)
        if original is None or deque is None:
            if original is None:
                raise AttributeError("send queue has no get")
            return await original()

        while True:
            if not deque:
                if ready is None:
                    return await original()
                ready.clear()
                await ready.wait()
                continue

            if self._rank_of(deque[0]) == 0:
                return await self._pack_prefix(original, deque, ready, 1, urgent=True)

            if self._pending_count() >= _MAX_SENDER_PENDING:
                changed = getattr(self._pending, "changed", None)
                if changed is None:
                    return await self._pack_prefix(
                        original, deque, ready, 1, urgent=False
                    )
                changed.clear()
                if deque and self._rank_of(deque[0]) == 0:
                    continue
                if self._pending_count() < _MAX_SENDER_PENDING:
                    continue
                await changed.wait()
                continue

            return await self._pack_prefix(
                original, deque, ready, _NON_URGENT_BATCH, urgent=False
            )

    async def _pack_prefix(self, original, deque, ready, limit, urgent):
        taken = []
        parked = []
        while deque and len(taken) < limit:
            item = deque.popleft()
            if not urgent and self._rank_of(item) == 0:
                deque.appendleft(item)
                break
            taken.append(item)
        while deque:
            parked.append(deque.popleft())
        for item in taken:
            deque.append(item)
        try:
            now = time.perf_counter()
            pending = self._pending_count()
            for item in taken:
                queued = self._enqueued_at.pop(id(item), now)
                queue_wait_ms = max(0.0, (now - queued) * 1000)
                route_type = _route_type(item, urgent)
                _log(
                    self._logger,
                    _sender_route_line(
                        route_type=route_type,
                        urgent=urgent,
                        sender_pending=pending,
                        queue_wait_ms=queue_wait_ms,
                        cut_ahead=urgent,
                    ),
                )
                if urgent and queue_wait_ms >= _URGENT_WAIT_LOG_MS:
                    reason = _wait_reason(True, pending, parked, queue_wait_ms)
                    _log(
                        self._logger,
                        "SENDER ROUTE WAIT "
                        f"type={route_type} urgent=True "
                        f"sender_pending={pending} "
                        f"queue_wait_ms={queue_wait_ms:.1f} "
                        f"reason={reason} parked={len(parked)}",
                    )
            return await original()
        finally:
            for item in parked:
                deque.append(item)
            if parked and ready is not None:
                ready.set()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _wrap_packer(sender, logger):
    pending = _watch_pending(sender)
    packer = getattr(sender, "_send_queue", None)
    if packer is None:
        return False
    if isinstance(packer, _PrioritySendQueue):
        packer._pending = pending
        packer._logger = logger
        return False
    try:
        sender._send_queue = _PrioritySendQueue(
            packer, pending=pending, logger=logger
        )
    except (AttributeError, TypeError):
        return False
    _log(logger, "OUTGOING RPC packer priority installed")
    return True


def _wrap_reconnect(sender, logger):
    original = getattr(sender, "_reconnect", None)
    if original is None or getattr(original, _SENDER_MARKER, False):
        return False

    async def hooked(last_error):
        drop_invalid_pending(sender, logger)
        drop_stale_low_pending(sender, logger)
        return await original(last_error)

    if not asyncio.iscoroutinefunction(original):
        def sync_hooked(last_error):
            drop_invalid_pending(sender, logger)
            drop_stale_low_pending(sender, logger)
            return original(last_error)
        setattr(sync_hooked, _SENDER_MARKER, True)
        try:
            sender._reconnect = sync_hooked
            return True
        except (AttributeError, TypeError):
            return False

    setattr(hooked, _SENDER_MARKER, True)
    try:
        sender._reconnect = hooked
        return True
    except (AttributeError, TypeError):
        return False


def _ensure_sender_hooks(client, logger):
    sender = getattr(client, "_sender", None)
    if sender is None:
        return False
    if getattr(sender, _SENDER_MARKER, False):
        return True
    try:
        _wrap_packer(sender, logger)
    except Exception as error:
        _log(logger, f"OUTGOING RPC packer hook skipped: {error!r}")
    try:
        _wrap_reconnect(sender, logger)
    except Exception as error:
        _log(logger, f"OUTGOING RPC reconnect hook skipped: {error!r}")
    try:
        setattr(sender, _SENDER_MARKER, True)
    except (AttributeError, TypeError):
        pass
    return True


def _wrap_connect(client, logger):
    original = getattr(client, "connect", None)
    if original is None or getattr(original, _SENDER_MARKER, False):
        return False

    async def hooked(*args, **kwargs):
        result = await original(*args, **kwargs)
        try:
            _ensure_sender_hooks(client, logger)
        except Exception as error:
            _log(logger, f"OUTGOING RPC sender hooks skipped: {error!r}")
        return result

    if not asyncio.iscoroutinefunction(original):
        def sync_hooked(*args, **kwargs):
            result = original(*args, **kwargs)
            try:
                _ensure_sender_hooks(client, logger)
            except Exception as error:
                _log(logger, f"OUTGOING RPC sender hooks skipped: {error!r}")
            return result
        setattr(sync_hooked, _SENDER_MARKER, True)
        try:
            client.connect = sync_hooked
            return True
        except (AttributeError, TypeError):
            return False

    setattr(hooked, _SENDER_MARKER, True)
    try:
        client.connect = hooked
        return True
    except (AttributeError, TypeError):
        return False


def _wrap_send_message(client, logger):
    """Mark short user replies urgent at the client.send_message entry."""
    original = getattr(client, "send_message", None)
    if original is None or getattr(original, _SEND_MARKER, False):
        return False

    async def hooked(*args, **kwargs):
        already = current_priority()
        if already in {URGENT, HIGH, LOW, NORMAL}:
            return await original(*args, **kwargs)
        try:
            from modules.urgent_send import should_mark_send_urgent
        except Exception:
            return await original(*args, **kwargs)
        if not should_mark_send_urgent(args, kwargs):
            return await original(*args, **kwargs)
        token = _PRIORITY.set(URGENT)
        try:
            return await original(*args, **kwargs)
        finally:
            _PRIORITY.reset(token)

    if not asyncio.iscoroutinefunction(original):
        return False
    setattr(hooked, _SEND_MARKER, True)
    try:
        client.send_message = hooked
        return True
    except (AttributeError, TypeError):
        return False


def install(client, logger=None):
    """Install sender isolation + 404 cache. Safe to call more than once."""
    if getattr(client, _CLIENT_MARKER, False):
        _ensure_sender_hooks(client, logger)
        return False
    _wrap_call(client, logger)
    _wrap_send_message(client, logger)
    for name in ("delete_messages", "edit_permissions", "kick_participant"):
        _wrap_high_operation(client, name)
    _wrap_connect(client, logger)
    _ensure_sender_hooks(client, logger)
    try:
        setattr(client, _CLIENT_MARKER, True)
    except (AttributeError, TypeError):
        pass
    _log(logger, "OUTGOING RPC isolation installed")
    return True
