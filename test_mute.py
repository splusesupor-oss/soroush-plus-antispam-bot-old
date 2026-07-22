import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()
    await bot.initialize_client()
    await bot.client.connect()

    group_id = 9429374
    username = "amir1405a"

    try:
        user = await bot.client.get_entity(username)

        print("USER:", user.id)

        result = await bot.client.edit_permissions(
            group_id,
            user.id,
            send_messages=False
        )

        print("SUCCESS:", result)

    except Exception as e:
        import traceback
        traceback.print_exc()

    await bot.client.disconnect()

asyncio.run(main())
