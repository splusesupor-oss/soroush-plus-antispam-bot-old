import asyncio

delete_queue = []
delete_lock = asyncio.Lock()

async def add_delete(chat_id, message_id):
    async with delete_lock:
        delete_queue.append((chat_id, message_id))

async def process_delete(bot):
    while True:
        await asyncio.sleep(0.2)

        async with delete_lock:
            if not delete_queue:
                continue

            items = delete_queue[:100]
            del delete_queue[:100]

        groups = {}

        for chat_id, msg_id in items:
            groups.setdefault(chat_id, []).append(msg_id)

        for chat_id, ids in groups.items():
            try:
                await bot.client.delete_messages(
                    chat_id,
                    ids
                )
            except Exception as e:
                print("delete queue error:", e)
