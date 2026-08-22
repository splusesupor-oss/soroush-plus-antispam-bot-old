"""Stage-one delete router; no legacy handler is redirected yet."""
class DeleteRouter:
    def __init__(self, manager): self.manager = manager
    async def delete_background(self, chat_id, message_ids):
        return await self.manager.delete_background(chat_id, message_ids)
