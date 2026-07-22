import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()
    await bot.initialize_client()
    await bot.client.connect()

    print("📋 لیست گروه‌ها:")

    async for d in bot.client.iter_dialogs():
        if hasattr(d.entity, "title"):
            print("✅", d.name, "| ID:", d.entity.id)

    await bot.client.disconnect()

asyncio.run(main())
