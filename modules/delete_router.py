"""Feature-flagged background delete router."""
class DeleteRouter:
    def __init__(self, manager):
        self.manager = manager

    async def delete_background(self, chat_id, message_ids):
        logger = getattr(self.manager, "logger", None)
        method = getattr(logger, "log_info", None)
        if callable(method):
            method(
                "ROUTE background -> delete real "
                f"chat_id={chat_id} count={len(message_ids or ())}"
            )
        return await self.manager.delete_background(chat_id, message_ids)
