"""Centralized Cache Layer and Permission Circuit Breaker for SPlusthon workloads.

Provides:
1. ``PermissionCircuitBreaker``: Trips on ``ChatAdminRequiredError`` / permission
   denials per group to prevent doomed RPC retries and save network roundtrips.
2. ``TtlCache``: High-performance, thread-safe / asyncio-safe in-memory cache
   with automatic TTL expiration and capacity management.
"""

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    from modules.group_id import normalize_group_id
    _HAS_NORMALIZE = True
except ImportError:
    _HAS_NORMALIZE = False
    def normalize_group_id(value):
        try:
            return str(int(value))
        except Exception:
            return str(value)


def _safe_chat_key(chat_id) -> str:
    """Extract a canonical string key for any chat_id or InputPeer object."""
    if chat_id is None:
        return "0"
    for attr in ("channel_id", "chat_id", "user_id", "id"):
        try:
            val = getattr(chat_id, attr, None)
            if isinstance(val, int):
                return normalize_group_id(val) if _HAS_NORMALIZE else str(val)
            if val is not None:
                try:
                    ival = int(val)
                    return normalize_group_id(ival) if _HAS_NORMALIZE else str(ival)
                except Exception:
                    return str(val)
        except Exception:
            continue
    try:
        ival = int(chat_id)
        return normalize_group_id(ival) if _HAS_NORMALIZE else str(ival)
    except Exception:
        pass
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
    return str(chat_id)


class TtlCache:
    """In-memory key-value cache with per-item TTL and max size eviction."""

    def __init__(self, default_ttl: float = 300.0, max_size: int = 2000):
        self.default_ttl = float(default_ttl)
        self.max_size = int(max_size)
        self._data: OrderedDict[Any, Tuple[Any, float]] = OrderedDict()
        self.stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}

    def get(self, key: Any, default: Any = None) -> Any:
        now = time.monotonic()
        if key in self._data:
            val, expires_at = self._data[key]
            if expires_at > now:
                self._data.move_to_end(key)
                self.stats["hits"] += 1
                return val
            else:
                del self._data[key]
        self.stats["misses"] += 1
        return default

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        now = time.monotonic()
        effective_ttl = float(ttl) if ttl is not None else self.default_ttl
        expires_at = now + effective_ttl

        if key in self._data:
            del self._data[key]
        elif len(self._data) >= self.max_size:
            # Evict oldest entry
            self._data.popitem(last=False)
            self.stats["evictions"] += 1

        self._data[key] = (value, expires_at)
        self.stats["sets"] += 1

    def delete(self, key: Any) -> bool:
        if key in self._data:
            del self._data[key]
            return True
        return False

    def clear(self) -> None:
        self._data.clear()

    def cleanup_expired(self) -> int:
        now = time.monotonic()
        expired_keys = [k for k, (_v, exp) in self._data.items() if exp <= now]
        for k in expired_keys:
            del self._data[k]
        return len(expired_keys)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "size": len(self._data),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "stats": dict(self.stats),
        }


STATE_CLOSED = "CLOSED"      # Normal operation: bot has admin rights
STATE_OPEN = "OPEN"          # Tripped: bot lacks admin rights; block RPCs
STATE_HALF_OPEN = "HALF_OPEN"  # Testing: allow 1 probe operation


@dataclass
class BreakerRecord:
    state: str = STATE_CLOSED
    tripped_at: float = 0.0
    cooldown: float = 180.0
    failure_count: int = 0
    last_error: str = ""
    probe_in_flight: bool = False


class PermissionCircuitBreaker:
    """Circuit breaker per chat to prevent continuous failed admin RPCs.

    When ``ChatAdminRequiredError`` or user admin invalidation occurs in a group,
    this breaker trips to ``OPEN`` state for ``cooldown_seconds`` (default: 180s).
    During this window, subsequent moderation and deletion RPCs for that group
    fail-fast locally (0ms) instead of wasting 150-400ms on doomed network calls.
    """

    _instance = None

    def __init__(self, default_cooldown: float = 180.0, logger=None):
        self.default_cooldown = float(default_cooldown)
        self.logger = logger
        self._breakers: Dict[str, BreakerRecord] = {}
        self.stats = {
            "tripped": 0,
            "blocked_calls": 0,
            "recovered": 0,
            "probes_allowed": 0,
        }

    @classmethod
    def get_default(cls, logger=None):
        if cls._instance is None:
            cls._instance = cls(logger=logger)
        return cls._instance

    def can_execute(self, chat_id, action: str = "admin_action") -> bool:
        """Check if an administrative operation is permitted for this chat."""
        key = _safe_chat_key(chat_id)
        record = self._breakers.get(key)
        if record is None or record.state == STATE_CLOSED:
            return True

        now = time.monotonic()
        # If cooldown has elapsed, transition from OPEN to HALF_OPEN
        if record.state == STATE_OPEN:
            if now - record.tripped_at >= record.cooldown:
                record.state = STATE_HALF_OPEN
                record.probe_in_flight = True
                self.stats["probes_allowed"] += 1
                if self.logger:
                    self.logger.log_info(
                        f"CIRCUIT BREAKER HALF_OPEN chat_id={key} "
                        f"action={action} probing permission status"
                    )
                return True
            else:
                self.stats["blocked_calls"] += 1
                return False

        if record.state == STATE_HALF_OPEN:
            # Allow only one probe at a time; others fail fast
            if not record.probe_in_flight:
                record.probe_in_flight = True
                self.stats["probes_allowed"] += 1
                return True
            self.stats["blocked_calls"] += 1
            return False

        return True

    def record_success(self, chat_id) -> None:
        """Record successful execution of an admin operation, resetting breaker."""
        key = _safe_chat_key(chat_id)
        record = self._breakers.get(key)
        if record is not None and record.state != STATE_CLOSED:
            record.state = STATE_CLOSED
            record.failure_count = 0
            record.probe_in_flight = False
            self.stats["recovered"] += 1
            if self.logger:
                self.logger.log_info(
                    f"CIRCUIT BREAKER RECOVERED chat_id={key} "
                    "permissions confirmed, state reset to CLOSED"
                )

    def record_failure(
        self, chat_id, error=None, cooldown: Optional[float] = None
    ) -> None:
        """Trip circuit breaker to OPEN upon permission failure."""
        key = _safe_chat_key(chat_id)
        record = self._breakers.get(key)
        now = time.monotonic()
        err_str = str(error or "ChatAdminRequiredError")
        effective_cooldown = (
            float(cooldown) if cooldown is not None else self.default_cooldown
        )

        if record is None:
            record = BreakerRecord()
            self._breakers[key] = record

        record.state = STATE_OPEN
        record.tripped_at = now
        record.cooldown = effective_cooldown
        record.failure_count += 1
        record.last_error = err_str
        record.probe_in_flight = False
        self.stats["tripped"] += 1

        if self.logger:
            self.logger.log_error(
                f"CIRCUIT BREAKER TRIPPED chat_id={key} "
                f"cooldown={effective_cooldown:.0f}s error={err_str}"
            )

    def reset(self, chat_id=None) -> None:
        """Manually clear circuit breaker state for a chat or all chats."""
        if chat_id is None:
            self._breakers.clear()
        else:
            key = _safe_chat_key(chat_id)
            self._breakers.pop(key, None)

    def is_open(self, chat_id) -> bool:
        key = _safe_chat_key(chat_id)
        record = self._breakers.get(key)
        if record is None:
            return False
        if record.state == STATE_OPEN:
            return (time.monotonic() - record.tripped_at) < record.cooldown
        return False

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        active_tripped = {
            k: {
                "state": r.state,
                "remaining_s": max(0.0, r.cooldown - (now - r.tripped_at)),
                "failure_count": r.failure_count,
                "last_error": r.last_error,
            }
            for k, r in self._breakers.items()
            if r.state == STATE_OPEN and (now - r.tripped_at) < r.cooldown
        }
        return {
            "total_tracked": len(self._breakers),
            "active_open_breakers": len(active_tripped),
            "tripped_chats": active_tripped,
            "stats": dict(self.stats),
        }
