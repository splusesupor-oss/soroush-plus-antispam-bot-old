"""Stage-one management router."""
class ModerationRouter:
    def __init__(self, manager): self.manager = manager
    async def execute(self, request):
        return await self.manager.moderation_management(request)
