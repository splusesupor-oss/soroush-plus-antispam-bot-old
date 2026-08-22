"""Fair bot-level admission control for SPlusthon application RPCs.

SPlusthon uses one shared WebSocket/sender for sends, deletes, moderation and
entity/history reads.  Per-chat queues keep handlers isolated, but without a
connection-wide budget dozens of independent chats can still create a large
``_pending_state`` at once.  ``RpcGovernor`` applies backpressure immediately
before the active low-level ``client._call`` and never drops a request/result.

The governor deliberately sits *outside* the existing 60-second RPC timeout:
time spent waiting for admission is reported separately and does not consume
network response time.  A permit is released by the caller's ``finally`` on
success, error, timeout or cancellation.  Retry/FloodWait sleeps performed by
our queues happen after ``_call`` has returned/raised and therefore hold no
permit.
"""

import asyncio
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

try:
    from modules.group_id import normalize_group_id
except ImportError:  # pragma: no cover - standalone compatibility
    def normalize_group_id(value):
        try:
            return str(int(value))
        except Exception:
            return str(value)


P0_CRITICAL = 0
P1_DELETE = 1
P2_SEND = 2
P3_HEAVY = 3

_PRIORITY_LABELS = {
    P0_CRITICAL: "P0",
    P1_DELETE: "P1",
    P2_SEND: "P2",
    P3_HEAVY: "P3",
}

# Native role checks and synchronization requests must remain responsive.
_CRITICAL_REQUESTS = frozenset({
    "EditBannedRequest",
    "EditAdminRequest",
    "EditChatDefaultBannedRightsRequest",
    "DeleteChatUserRequest",
    "GetParticipantRequest",
    "GetStateRequest",
    "GetDifferenceRequest",
    "GetChannelDifferenceRequest",
    "GetConfigRequest",
    "PingRequest",
    "DestroySessionRequest",
    "ExportAuthorizationRequest",
    "ImportAuthorizationRequest",
})
_DELETE_REQUESTS = frozenset({
    "DeleteMessagesRequest",
    "DeleteHistoryRequest",
})
_SEND_REQUESTS = frozenset({
    "SendMessageRequest",
    "SendMediaRequest",
    "SendMultiMediaRequest",
    "ForwardMessagesRequest",
    "SendInlineBotResultRequest",
    "SaveFilePartRequest",
    "SaveBigFilePartRequest",
})
_HEAVY_REQUESTS = frozenset({
    "GetHistoryRequest",
    "GetMessagesRequest",
    "GetParticipantsRequest",
    "GetFullChannelRequest",
    "GetFullChatRequest",
    "GetChannelsRequest",
    "GetChatsRequest",
    "GetUsersRequest",
})


@dataclass(frozen=True)
class RpcAdmission:
    priority: int
    bucket: str
    request_name: str
    chat_key: str


@dataclass
class _Waiter:
    priority: int
    bucket: str
    request_name: str
    chat_key: str
    future: object
    enqueued_at: float
    sequence: int
    admitted: bool = False


class RpcOverloadError(RuntimeError):
    """A disposable low-priority RPC was rejected before it could backlog."""


class RpcPermit:
    """One governor admission. ``release`` is idempotent."""

    __slots__ = ("_governor", "priority", "bucket", "shadow", "released")

    def __init__(self, governor, priority, bucket, *, shadow=False):
        self._governor = governor
        self.priority = int(priority)
        self.bucket = str(bucket)
        self.shadow = bool(shadow)
        self.released = False

    def release(self):
        if self.released:
            return False
        self.released = True
        self._governor._release(self.priority, self.bucket)
        return True

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        self.release()


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return bool(default)
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name, default, minimum=1):
    try:
        return max(int(minimum), int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return int(default)


def _env_float(name, default, minimum=0.0):
    try:
        return max(float(minimum), float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return float(default)


def _unwrap_requests(request):
    """Yield real TL requests through list/Invoke wrappers without mutation."""
    pending = deque([request])
    seen = set()
    while pending:
        current = pending.popleft()
        if current is None:
            continue
        if isinstance(current, (list, tuple)):
            pending.extend(current)
            continue
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        inner = getattr(current, "query", None)
        if inner is not None:
            pending.appendleft(inner)
            continue
        yield current


def _request_chat(request):
    for current in _unwrap_requests(request):
        for attr in ("peer", "channel", "entity", "chat_id"):
            value = getattr(current, attr, None)
            if value is None:
                continue
            for nested in ("channel_id", "chat_id", "user_id", "id"):
                found = getattr(value, nested, None)
                if found is not None:
                    return found
            if isinstance(value, (int, str)):
                return value
    return None


def _stable_chat_key(value):
    if value is None:
        return "global"
    try:
        return normalize_group_id(value)
    except Exception:
        try:
            return str(value)
        except Exception:
            return "global"


def classify_request(request, *, urgent_send=False, critical_context=False):
    """Classify a SPlusthon TL request using names stable across versions."""
    names = [type(item).__name__ for item in _unwrap_requests(request)]
    if not names:
        names = [type(request).__name__]

    name_set = set(names)
    if name_set.intersection(_CRITICAL_REQUESTS):
        priority, bucket = P0_CRITICAL, "critical"
    elif name_set.intersection(_DELETE_REQUESTS):
        # Even a manual/admin delete stays P1. Queue workers inherit the
        # context in which they were created; allowing that inherited context
        # to turn a long deletion wave into P0 would defeat the reserved slots.
        priority, bucket = P1_DELETE, "delete"
    elif name_set.intersection(_SEND_REQUESTS):
        # A direct user/admin command reply is explicitly marked by the
        # command handler.  It must run ahead of cosmetic/automatic notices;
        # otherwise a delete burst makes «راهنما» appear to be ignored.
        if urgent_send:
            priority, bucket = P0_CRITICAL, "critical"
        else:
            priority, bucket = P2_SEND, "send"
    # Reads are never promoted by a command's dispatch context.  A native
    # admin lookup (GetParticipants/GetFullChannel) is expensive and was
    # filling every P0 slot ahead of the actual mute/ban RPC.
    elif name_set.intersection(_HEAVY_REQUESTS) or any(
        name.startswith(("Get", "Search")) for name in names
    ):
        priority, bucket = P3_HEAVY, "heavy"
    elif critical_context:
        priority, bucket = P0_CRITICAL, "critical"
    else:
        # Unknown application calls are limited by the combined noncritical
        # budget, but do not inherit the strict heavy-read cap.
        priority, bucket = P2_SEND, "other"

    return RpcAdmission(
        priority=priority,
        bucket=bucket,
        request_name="+".join(names[:3]),
        chat_key=_stable_chat_key(_request_chat(request)),
    )


class RpcGovernor:
    """Fixed-limit, priority-aware and per-chat-fair RPC admission control."""

    # P0 is always considered first. Noncritical traffic uses a weighted
    # cycle: security deletion gets more turns, while P2/P3 cannot starve.
    _NONCRITICAL_CYCLE = (
        P1_DELETE, P2_SEND, P1_DELETE, P2_SEND, P1_DELETE, P3_HEAVY,
    )

    def __init__(
        self,
        *,
        total_limit=2,
        noncritical_limit=1,
        delete_limit=1,
        send_limit=1,
        heavy_limit=1,
        enabled=True,
        shadow=False,
        logger=None,
        wait_log_ms=20.0,
        max_send_waiters=4,
    ):
        self.total_limit = max(1, int(total_limit))
        self.noncritical_limit = max(
            1, min(int(noncritical_limit), self.total_limit)
        )
        self.class_limits = {
            "delete": max(1, int(delete_limit)),
            "send": max(1, int(send_limit)),
            "heavy": max(1, int(heavy_limit)),
        }
        self.enabled = bool(enabled)
        self.shadow = bool(shadow)
        self.logger = logger
        self.wait_log_ms = max(0.0, float(wait_log_ms))
        self.max_send_waiters = max(0, int(max_send_waiters))

        self._active_total = 0
        self._active_noncritical = 0
        self._active_by_bucket = defaultdict(int)
        self._queues = {priority: {} for priority in range(4)}
        self._chat_rounds = {priority: deque() for priority in range(4)}
        self._sequence = 0
        self._noncritical_cursor = 0
        self._waiting = 0
        self._max_waiting = 0
        self.stats = {
            "admitted": 0,
            "released": 0,
            "waited": 0,
            "cancelled_waiters": 0,
            "shadow_would_wait": 0,
        }

    @classmethod
    def from_environment(cls, logger=None):
        """Build conservative fixed limits after the project's .env is loaded."""
        return cls(
            # A single Soroush connection becomes unstable above these caps;
            # retain env configurability only for making limits stricter.
            total_limit=min(2, _env_int("BOT_RPC_TOTAL_LIMIT", 2)),
            noncritical_limit=min(1, _env_int("BOT_RPC_NONCRITICAL_LIMIT", 1)),
            delete_limit=min(1, _env_int("BOT_RPC_DELETE_LIMIT", 1)),
            send_limit=min(1, _env_int("BOT_RPC_SEND_LIMIT", 1)),
            heavy_limit=_env_int("BOT_RPC_HEAVY_LIMIT", 1),
            enabled=_env_bool("BOT_RPC_GOVERNOR_ENABLED", True),
            shadow=_env_bool("BOT_RPC_GOVERNOR_SHADOW", False),
            logger=logger,
            wait_log_ms=_env_float("BOT_RPC_WAIT_LOG_MS", 20.0),
            # A zero-length send queue drops every reply whenever one delete,
            # read or moderation RPC is active. Keep this bounded, but allow
            # public commands and help replies to wait for the shared session.
            max_send_waiters=max(2, _env_int("BOT_RPC_MAX_SEND_WAITERS", 4)),
        )

    @property
    def active(self):
        return self._active_total

    @property
    def waiting(self):
        return self._waiting

    def _eligible(self, priority, bucket):
        if self._active_total >= self.total_limit:
            return False
        if priority != P0_CRITICAL:
            if self._active_noncritical >= self.noncritical_limit:
                return False
            cap = self.class_limits.get(bucket)
            if cap is not None and self._active_by_bucket[bucket] >= cap:
                return False
        return True

    def _increment_active(self, priority, bucket):
        self._active_total += 1
        if priority != P0_CRITICAL:
            self._active_noncritical += 1
        self._active_by_bucket[bucket] += 1
        self.stats["admitted"] += 1

    def _enqueue(self, waiter):
        groups = self._queues[waiter.priority]
        group = groups.get(waiter.chat_key)
        if group is None:
            group = groups[waiter.chat_key] = deque()
            self._chat_rounds[waiter.priority].append(waiter.chat_key)
        group.append(waiter)
        self._waiting += 1
        self._max_waiting = max(self._max_waiting, self._waiting)

    def _pop_priority(self, priority):
        """Pop one eligible waiter, round-robin between chats of a class."""
        rounds = self._chat_rounds[priority]
        groups = self._queues[priority]
        checks = len(rounds)
        for _ in range(checks):
            chat_key = rounds.popleft()
            group = groups.get(chat_key)
            if group is None:
                continue
            while group and group[0].future.done():
                group.popleft()
                self._waiting = max(0, self._waiting - 1)
            if not group:
                groups.pop(chat_key, None)
                continue
            waiter = group[0]
            if not self._eligible(waiter.priority, waiter.bucket):
                rounds.append(chat_key)
                continue
            group.popleft()
            self._waiting = max(0, self._waiting - 1)
            if group:
                rounds.append(chat_key)
            else:
                groups.pop(chat_key, None)
            return waiter
        return None

    def _pop_noncritical(self):
        cycle = self._NONCRITICAL_CYCLE
        for _ in range(len(cycle)):
            priority = cycle[self._noncritical_cursor]
            self._noncritical_cursor = (self._noncritical_cursor + 1) % len(cycle)
            waiter = self._pop_priority(priority)
            if waiter is not None:
                return waiter
        return None

    def _drain(self):
        if not self.enabled or self.shadow:
            return
        while self._active_total < self.total_limit:
            waiter = self._pop_priority(P0_CRITICAL)
            if waiter is None:
                waiter = self._pop_noncritical()
            if waiter is None:
                return
            if waiter.future.done():
                continue
            waiter.admitted = True
            self._increment_active(waiter.priority, waiter.bucket)
            permit = RpcPermit(self, waiter.priority, waiter.bucket)
            waiter.future.set_result(permit)

    async def acquire(self, admission):
        """Wait for admission, or only observe limits in shadow mode."""
        if not isinstance(admission, RpcAdmission):
            raise TypeError("admission must be RpcAdmission")
        # Sending a cosmetic/game response after it sat behind five RPCs is
        # worse than dropping it: it prolongs the backlog and delays mute/ban.
        # Only shed ordinary/background sends. Command and moderation replies
        # are P0 and must remain deliverable even while normal notifications
        # have already filled the send backlog.
        if (not self.shadow and admission.bucket == "send"
                and admission.priority != P0_CRITICAL
                and self._waiting >= self.max_send_waiters):
            raise RpcOverloadError("outgoing send backlog is full")

        if not self.enabled and not self.shadow:
            # Wrapper normally bypasses this mode. Keep direct use harmless.
            self._increment_active(admission.priority, admission.bucket)
            return RpcPermit(self, admission.priority, admission.bucket)

        if self.shadow:
            if not self._eligible(admission.priority, admission.bucket):
                self.stats["shadow_would_wait"] += 1
            self._increment_active(admission.priority, admission.bucket)
            return RpcPermit(
                self, admission.priority, admission.bucket, shadow=True
            )

        loop = asyncio.get_running_loop()
        self._sequence += 1
        waiter = _Waiter(
            priority=admission.priority,
            bucket=admission.bucket,
            request_name=admission.request_name,
            chat_key=admission.chat_key,
            future=loop.create_future(),
            enqueued_at=time.perf_counter(),
            sequence=self._sequence,
        )
        self._enqueue(waiter)
        self._drain()
        try:
            permit = await waiter.future
        except asyncio.CancelledError:
            self.stats["cancelled_waiters"] += 1
            if waiter.admitted:
                # Cancellation can land after set_result but before this task
                # resumes. Return the transferred slot immediately.
                try:
                    waiter.future.result().release()
                except Exception:
                    pass
            # A cancelled future is lazily removed by the next drain.
            self._drain()
            raise

        wait_ms = (time.perf_counter() - waiter.enqueued_at) * 1000
        if wait_ms >= self.wait_log_ms:
            self.stats["waited"] += 1
            if self.logger is not None:
                self.logger.log_info(
                    "RPC GOVERNOR WAIT "
                    f"request={admission.request_name} "
                    f"priority={_PRIORITY_LABELS[admission.priority]} "
                    f"bucket={admission.bucket} chat={admission.chat_key} "
                    f"wait_ms={wait_ms:.1f} active={self._active_total} "
                    f"waiting={self._waiting}"
                )
        return permit

    def _release(self, priority, bucket):
        if self._active_total > 0:
            self._active_total -= 1
        if priority != P0_CRITICAL and self._active_noncritical > 0:
            self._active_noncritical -= 1
        if self._active_by_bucket.get(bucket, 0) > 0:
            self._active_by_bucket[bucket] -= 1
        self.stats["released"] += 1
        self._drain()

    def snapshot(self):
        waiting_by_priority = {}
        for priority, groups in self._queues.items():
            waiting_by_priority[_PRIORITY_LABELS[priority]] = sum(
                sum(1 for waiter in group if not waiter.future.done())
                for group in groups.values()
            )
        return {
            "enabled": self.enabled,
            "shadow": self.shadow,
            "total_limit": self.total_limit,
            "noncritical_limit": self.noncritical_limit,
            "active": self._active_total,
            "active_noncritical": self._active_noncritical,
            "active_by_bucket": dict(self._active_by_bucket),
            "waiting": sum(waiting_by_priority.values()),
            "waiting_by_priority": waiting_by_priority,
            "max_waiting": self._max_waiting,
            "stats": dict(self.stats),
        }

    def mode_label(self):
        if self.shadow:
            return "shadow"
        return "enabled" if self.enabled else "disabled"
