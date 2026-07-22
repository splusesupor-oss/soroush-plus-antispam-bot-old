import asyncio
from core.bot_working_split_ok import SoroushAntiSpamBot

async def test():

    bot = SoroushAntiSpamBot()

    try:
        await bot.initialize_client()
        await bot.client.connect()

        chat_id = -1000023093376

        users = await bot.client.get_participants(chat_id)

        print("COUNT:", len(users))

        for u in users:
            print("----")
            print("ID:", getattr(u, "id", None))
            print("USER:", getattr(u, "username", None))
            print("CREATOR:", getattr(u, "is_creator", None))
            print("ADMIN:", getattr(u, "admin_rights", None))

    except Exception as e:
        print("ERROR:", e)

    finally:
        try:
            await bot.client.disconnect()
        except:
            pass


asyncio.run(test())
