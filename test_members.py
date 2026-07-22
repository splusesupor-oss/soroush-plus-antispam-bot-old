import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()

    await bot.initialize_client()
    await bot.client.connect()

    try:
        group = None

        async for dialog in bot.client.iter_dialogs():
            if getattr(dialog.entity, "id", None) == 9429374:
                group = dialog.entity
                break

        print("GROUP:", group.title)

        users = await bot.client.get_participants(group)

        print("COUNT:", len(users))

        for u in users[:10]:
            print(
                u.id,
                getattr(u, "username", None),
                getattr(u, "first_name", None)
            )

    except Exception as e:
        print("ERROR:", e)

    await bot.client.disconnect()

asyncio.run(main())
