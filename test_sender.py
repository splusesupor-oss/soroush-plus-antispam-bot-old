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

        async for msg in bot.client.iter_messages(group, limit=5):
            print("MSG:", msg.message)

            try:
                sender = await msg.get_sender()
                print("SENDER:", sender)
                print("ID:", getattr(sender, "id", None))
                print("ADMIN:", getattr(sender, "admin_rights", None))
                print("CREATOR:", getattr(sender, "creator", None))
            except Exception as e:
                print("SENDER ERROR:", e)

            print("----------------")

    except Exception as e:
        print("ERROR:", e)

    await bot.client.disconnect()

asyncio.run(main())
