import asyncio
from datetime import datetime, timedelta

class GroupControl:
    def __init__(self, client):
        self.client = client
        self.lock_tasks = {}

    async def lock_group(self, chat_id):
        await self.client.edit_permissions(
            chat_id,
            send_messages=False
        )
        return True

    async def unlock_group(self, chat_id):
        await self.client.edit_permissions(
            chat_id,
            send_messages=True
        )
        return True

    async def timed_lock(self, chat_id, minutes):
        await self.lock_group(chat_id)

        async def unlock_later():
            await asyncio.sleep(minutes * 60)
            await self.unlock_group(chat_id)

        task = asyncio.create_task(unlock_later())
        self.lock_tasks[str(chat_id)] = task
        return True

    async def change_title(self, chat_id, title):
        from splusthon.tl.functions.channels import EditTitleRequest

        await self.client(
            EditTitleRequest(
                channel=chat_id,
                title=title
            )
        )
        return True
