from pathlib import Path

p = Path("modules/delete_queue.py")

p.write_text("""
import asyncio
from collections import defaultdict

class DeleteQueue:

    def __init__(self, client):
        self.client = client
        self.queues = defaultdict(list)

    async def add(self, chat_id, message_id):
        self.queues[chat_id].append(message_id)

    async def delete_now(self, chat_id):
        ids = self.queues.get(chat_id, [])

        if not ids:
            return

        self.queues[chat_id] = []

        for i in range(0, len(ids), 100):
            batch = ids[i:i+100]
            try:
                await self.client.delete_messages(
                    chat_id,
                    batch
                )
            except Exception as e:
                print("delete queue error:", e)
""", encoding="utf-8")

print("✅ delete_queue.py created")
