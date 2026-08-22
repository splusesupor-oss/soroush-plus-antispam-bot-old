"""Stage-one public reply router; not installed on handlers yet."""
from __future__ import annotations
from typing import Any


class ReplyRouter:
    def __init__(self, manager):
        self.manager = manager

    def observe_public_route(self, event: Any) -> str:
        """Dry-run only: record the future route without sending an RPC."""
        logger = getattr(self.manager, "logger", None)
        method = getattr(logger, "log_info", None)
        if callable(method):
            method(
                "ROUTE background -> reply "
                f"dry_run=True chat_id={getattr(event, 'chat_id', None)}"
            )
        return "background"

    async def send_public(self, event: Any, text: str, **kwargs):
        chat_id = getattr(event, "chat_id", None)
        reply_to = kwargs.pop("reply_to", None)
        if reply_to is None:
            reply_to = getattr(getattr(event, "message", None), "id", None)
        if reply_to is not None:
            kwargs["reply_to"] = reply_to
        return await self.manager.send_background(chat_id, text, **kwargs)
