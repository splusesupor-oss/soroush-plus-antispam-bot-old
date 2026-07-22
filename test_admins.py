import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()

    await bot.initialize_client()
    await bot.client.connect()

    chat_id = 9429374

    try:
        group = await bot.client.get_entity(chat_id)

        print("GROUP OK:", getattr(group, "title", None))

        admins = await bot.client.get_participants(
            group,
            filter="admins"
        )

        print("✅ تعداد ادمین‌ها:", len(admins))

        for a in admins:
            print(
                "ID:",
                a.id,
                "USER:",
                getattr(a, "username", None),
                "NAME:",
                getattr(a, "first_name", None)
            )

    except Exception as e:
        print("❌ خطا:", e)

    await bot.client.disconnect()

asyncio.run(main())
