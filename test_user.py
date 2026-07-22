import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()
    await bot.initialize_client()
    await bot.client.connect()

    username = "amir1405a"

    try:
        user = await bot.client.get_entity(username)
        print("USER FOUND:")
        print(user)
    except Exception as e:
        print("USER ERROR:", e)

    await bot.client.disconnect()

asyncio.run(main())
