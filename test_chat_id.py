import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()
    await bot.initialize_client()

    async for msg in bot.client.iter_messages("𝗚𝗿𝗼𝘂𝗽 𝗳𝗼𝘅", limit=1):
        print("CHAT_ID:", getattr(msg, "chat_id", None))
        print("PEER:", getattr(msg, "peer_id", None))
        print("MESSAGE_ID:", msg.id)
        break

asyncio.run(main())
