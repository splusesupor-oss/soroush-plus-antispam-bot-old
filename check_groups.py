import asyncio
from main import SoroushAntiSpamBot

async def test():
    bot = SoroushAntiSpamBot()
    await bot.initialize_client()
    await bot.client.connect()

    print("=== GROUP TEST ===")

    async for d in bot.client.iter_dialogs():
        entity = d.entity

        print("\n---")
        print("TYPE:", type(entity))
        print("TITLE:", getattr(entity, "title", None))
        print("ID:", getattr(entity, "id", None))
        print("USERNAME:", getattr(entity, "username", None))
        print("ACCESS_HASH:", getattr(entity, "access_hash", None))
        print("ATTRS:", entity.__dict__)

    await bot.client.disconnect()

asyncio.run(test())
