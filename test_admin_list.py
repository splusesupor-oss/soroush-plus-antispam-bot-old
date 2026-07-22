import asyncio
from core.bot_working_split_ok import SoroushAntiSpamBot
from splusthon.tl.types import ChannelParticipantsAdmins

async def main():

    bot = SoroushAntiSpamBot()

    try:
        await bot.initialize_client()
        await bot.client.connect()

        chat_id = -1000023093376

        print("ADMINS:")

        async for user in bot.client.iter_participants(
            chat_id,
            filter=ChannelParticipantsAdmins
        ):
            print(
                user.id,
                getattr(user, "username", None),
                getattr(user, "first_name", None)
            )

    except Exception as e:
        print("ERROR:", e)

    finally:
        try:
            await bot.client.disconnect()
        except:
            pass


asyncio.run(main())
