"""Resolve the configured global owner as a private *user* peer only.

A bare positive integer passed to SPlusthon may fall through to
``GetUsersRequest(InputUser(id, access_hash=0))`` and fail with ``NOT_FOUND``.
For this user-bot the global owner is normally the logged-in account itself, so
we first use ``get_me(input_peer=True)``.  That returns a concrete user input
peer with the correct access hash and cannot be reinterpreted as a group.
"""
from __future__ import annotations

import inspect
import traceback
from typing import Any, List, Optional

from modules.owner_check import get_owner


class OwnerPrivateResolveError(RuntimeError):
    """No safe private-user peer could be resolved for the configured owner."""


def _log(logger: Any, level: str, message: str) -> None:
    if logger is None:
        return
    method = getattr(logger, "log_error" if level == "error" else "log_info", None)
    if callable(method):
        method(message)


def peer_user_id(peer: Any) -> Optional[int]:
    if peer is None:
        return None
    if getattr(peer, "channel_id", None) is not None:
        return None
    if getattr(peer, "chat_id", None) is not None:
        return None
    value = getattr(peer, "user_id", getattr(peer, "id", None))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validated_user_peer(peer: Any, owner_id: int, method: str) -> Any:
    if peer is None:
        raise OwnerPrivateResolveError(f"{method} returned None")
    if getattr(peer, "channel_id", None) is not None:
        raise OwnerPrivateResolveError(
            f"{method} resolved owner as channel peer"
        )
    if getattr(peer, "chat_id", None) is not None:
        raise OwnerPrivateResolveError(
            f"{method} resolved owner as chat peer"
        )
    peer_id = peer_user_id(peer)
    if peer_id != int(owner_id):
        raise OwnerPrivateResolveError(
            f"{method} user mismatch: expected={owner_id} actual={peer_id} "
            f"peer_type={peer.__class__.__name__}"
        )
    return peer


def _attempt_text(method: str, error: BaseException) -> str:
    return (
        f"method={method} error_type={type(error).__name__} "
        f"error={error!r}"
    )


def current_owner_user_id() -> int:
    """Read the sole owner authority through ``get_owner()``."""
    owner = get_owner()
    if not isinstance(owner, dict) or owner.get("user_id") is None:
        raise OwnerPrivateResolveError("global owner is not configured")
    try:
        owner_id = int(owner["user_id"])
    except (TypeError, ValueError) as error:
        raise OwnerPrivateResolveError("global owner user_id is invalid") from error
    if owner_id <= 0:
        raise OwnerPrivateResolveError("global owner user_id must be positive")
    return owner_id


async def resolve_private_owner_peer(
    client: Any,
    *,
    logger: Any = None,
    context: str = "OWNER_REPORT",
) -> Any:
    """Return only a concrete private-user peer for the current ``get_owner()``.

    Resolution order is deliberately user-only:

    1. logged-in self peer with a valid access hash;
    2. SPlusthon in-memory user cache;
    3. session user cache;
    4. explicit ``PeerUser(owner_id)`` network fallback.

    The final fallback may internally use ``GetUsersRequest``.  If it fails,
    the complete traceback, owner ID and method are logged as requested.
    """
    # Do not accept an owner ID from callers.  This prevents stale runtime or
    # legacy call sites from injecting a former owner into report delivery.
    configured_owner_id = current_owner_user_id()
    attempts: List[str] = []

    # Expected production path: osine2 is the logged-in user-bot account.
    method = "get_me(input_peer=True)"
    get_me = getattr(client, "get_me", None)
    if callable(get_me):
        try:
            candidate = get_me(input_peer=True)
            if inspect.isawaitable(candidate):
                candidate = await candidate
            target = _validated_user_peer(candidate, configured_owner_id, method)
            _log(
                logger,
                "info",
                f"{context} OWNER PRIVATE RESOLVED "
                f"owner_id={configured_owner_id} method={method} "
                f"peer_type={target.__class__.__name__}",
            )
            return target
        except Exception as error:
            attempts.append(_attempt_text(method, error))
    else:
        attempts.append(f"method={method} error=get_me_unavailable")

    # Cache-only path: never makes GetUsersRequest and never guesses chat type.
    method = "memory_entity_cache(user_id)"
    try:
        cache = getattr(client, "_mb_entity_cache", None)
        if cache is None:
            raise OwnerPrivateResolveError("memory entity cache unavailable")
        entry = cache.get(configured_owner_id)
        if entry is None:
            raise OwnerPrivateResolveError("owner absent from memory entity cache")
        candidate = entry._as_input_peer()
        target = _validated_user_peer(candidate, configured_owner_id, method)
        _log(
            logger,
            "info",
            f"{context} OWNER PRIVATE RESOLVED "
            f"owner_id={configured_owner_id} method={method} "
            f"peer_type={target.__class__.__name__}",
        )
        return target
    except Exception as error:
        attempts.append(_attempt_text(method, error))

    # Persistent session cache, constrained explicitly to PeerUser.
    method = "session.get_input_entity(PeerUser)"
    try:
        from splusthon import types

        session = getattr(client, "session", None)
        resolver = getattr(session, "get_input_entity", None)
        if not callable(resolver):
            raise OwnerPrivateResolveError("session entity cache unavailable")
        candidate = resolver(types.PeerUser(configured_owner_id))
        if inspect.isawaitable(candidate):
            candidate = await candidate
        target = _validated_user_peer(candidate, configured_owner_id, method)
        _log(
            logger,
            "info",
            f"{context} OWNER PRIVATE RESOLVED "
            f"owner_id={configured_owner_id} method={method} "
            f"peer_type={target.__class__.__name__}",
        )
        return target
    except Exception as error:
        attempts.append(_attempt_text(method, error))

    # Last resort. Passing PeerUser prevents positive ID ambiguity. If the
    # access hash is absent SPlusthon may issue GetUsersRequest; retain its full
    # failure instead of silently retrying the raw integer as before.
    method = "get_input_entity(PeerUser)"
    try:
        from splusthon import types

        resolver = getattr(client, "get_input_entity", None)
        if not callable(resolver):
            raise OwnerPrivateResolveError("client resolver unavailable")
        candidate = resolver(types.PeerUser(configured_owner_id))
        if inspect.isawaitable(candidate):
            candidate = await candidate
        target = _validated_user_peer(candidate, configured_owner_id, method)
        _log(
            logger,
            "info",
            f"{context} OWNER PRIVATE RESOLVED "
            f"owner_id={configured_owner_id} method={method} "
            f"peer_type={target.__class__.__name__}",
        )
        return target
    except Exception as error:
        attempts.append(_attempt_text(method, error))
        full_traceback = traceback.format_exc()
        _log(
            logger,
            "error",
            f"{context} OWNER PRIVATE RESOLVE FAILED "
            f"owner_id={configured_owner_id} method={method} "
            f"error_type={type(error).__name__} error={error!r} "
            f"attempts={' | '.join(attempts)}\n"
            f"traceback={full_traceback}",
        )
        raise OwnerPrivateResolveError(
            f"could not resolve private owner user_id={configured_owner_id}; "
            f"last_method={method}; error={error!r}"
        ) from error
