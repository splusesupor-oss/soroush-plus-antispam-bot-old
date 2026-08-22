"""Three-session client ownership and routing primitives.

This module intentionally does not patch handlers.  It is stage-one
infrastructure: routing is explicit, testable, and has no implicit fallback.
"""
from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any, Awaitable, Callable, Optional


class ClientRouteError(RuntimeError):
    pass


class ClientManager:
    ROLES = ("primary", "management", "background")

    def __init__(
        self,
        primary_client: Any,
        *,
        management_factory: Optional[Callable[[], Any]] = None,
        background_factory: Optional[Callable[[], Any]] = None,
        logger: Any = None,
        enabled: Optional[bool] = None,
    ):
        self.primary_client = primary_client
        self.management_client = None
        self.background_client = None
        self._factories = {
            "management": management_factory,
            "background": background_factory,
        }
        self.logger = logger
        self.enabled = (
            os.getenv("BOT_MULTI_CLIENT_ENABLED", "0").strip().lower()
            in {"1", "true", "yes", "on"}
            if enabled is None else bool(enabled)
        )

    def _log(self, message: str, *, error: bool = False) -> None:
        method = getattr(self.logger, "log_error" if error else "log_info", None)
        if callable(method):
            method(message)

    def client_for(self, role: str) -> Any:
        if role == "primary":
            return self.primary_client
        client = getattr(self, f"{role}_client", None)
        if client is None:
            raise ClientRouteError(f"ROUTE {role} unavailable; no fallback")
        return client

    def observe_routes(self) -> None:
        """Emit no-RPC route telemetry for stage-two verification."""
        self._log("ROUTE primary -> receive dry_run=True")
        self._log("ROUTE management -> moderation dry_run=True")
        self._log("ROUTE background -> reply/delete dry_run=True")

    async def connect_workers(self) -> bool:
        if not self.enabled:
            self._log("CLIENT MANAGER safe_single_client_mode enabled")
            return False
        ready = True
        for role in ("management", "background"):
            factory = self._factories[role]
            if not callable(factory):
                self._log(f"CLIENT {role} unavailable: factory missing", error=True)
                ready = False
                continue
            try:
                client = factory()
                result = client.connect()
                if inspect.isawaitable(result):
                    await result
                setattr(self, f"{role}_client", client)
                self._log(f"CLIENT READY role={role}")
            except Exception as error:
                # Do not touch primary or the other worker.
                self._log(f"CLIENT FAILED role={role} error={error!r}", error=True)
                ready = False
        return ready

    async def connect_role(self, role: str) -> bool:
        """Connect exactly one worker; never affects any other role."""
        if role not in {"management", "background"}:
            raise ClientRouteError(f"invalid worker role={role}")
        factory = self._factories[role]
        if not callable(factory):
            self._log(f"CLIENT {role} unavailable: factory missing", error=True)
            return False
        try:
            client = factory()
            result = client.connect()
            if inspect.isawaitable(result):
                await result
            setattr(self, f"{role}_client", client)
            self._log(f"CLIENT READY role={role}")
            return True
        except Exception as error:
            self._log(f"CLIENT FAILED role={role} error={error!r}", error=True)
            return False

    async def disconnect_role(self, role: str) -> None:
        if role == "primary":
            raise ClientRouteError("primary is owned by the receiver")
        client = getattr(self, f"{role}_client", None)
        if client is None:
            return
        try:
            result = client.disconnect()
            if inspect.isawaitable(result):
                await result
        finally:
            setattr(self, f"{role}_client", None)

    async def _call(self, role: str, method: str, *args, **kwargs):
        client = self.client_for(role)
        self._log(f"ROUTE {role} -> {method}")
        target = getattr(client, method, None)
        if not callable(target):
            raise ClientRouteError(f"ROUTE {role} missing method={method}")
        result = target(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

    async def send_primary(self, *args, **kwargs):
        return await self._call("primary", "send_message", *args, **kwargs)

    async def send_management(self, *args, **kwargs):
        return await self._call("management", "send_message", *args, **kwargs)

    async def send_background(self, *args, **kwargs):
        return await self._call("background", "send_message", *args, **kwargs)

    async def delete_background(self, *args, **kwargs):
        return await self._call("background", "delete_messages", *args, **kwargs)

    async def moderation_management(self, request: Any):
        return await self._call("management", "__call__", request)
