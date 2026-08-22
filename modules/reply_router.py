"""Stage-one public reply router; not installed on handlers yet."""
from __future__ import annotations
from typing import Any


class ReplyRouter:
    def __init__(self, manager):
        self.manager = manager

    async def send_public(self, event: Any, text: str, **kwargs):
        chat_id = getattr(event, "chat_id", None)
        reply_to = kwargs.pop("reply_to", None)
        if reply_to is None:
            reply_to = getattr(getattr(event, "message", None), "id", None)
        if reply_to is not None:
            kwargs["reply_to"] = reply_to
        return await self.manager.send_background(chat_id, text, **kwargs)
