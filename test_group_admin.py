import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()

    await bot.initialize_client()
    await bot.client.connect()

    try:
        group = await bot.client.get_entity(9429374)

        print("TITLE:", group.title)
        print("ADMIN RIGHTS:")
        print(getattr(group, "admin_rights", None))

        print("CREATOR:")
        print(getattr(group, "creator", None))

    except Exception as e:
        print("ERROR:", e)

    await bot.client.disconnect()

asyncio.run(main())
