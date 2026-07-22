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

        if not group:
            print("❌ گروه در دیالوگ‌ها پیدا نشد")
            return

        print("✅ گروه پیدا شد:", group.title)

        admins = await bot.client.get_participants(
            group,
            filter="admins"
        )

        print("تعداد:", len(admins))

        for a in admins:
            print(a.id, getattr(a, "username", None))

    except Exception as e:
        print("❌ خطا:", e)

    await bot.client.disconnect()

asyncio.run(main())
