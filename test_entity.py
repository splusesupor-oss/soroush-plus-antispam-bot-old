import asyncio
from core.bot_working_split_ok import SoroushAntiSpamBot

async def main():

    bot = SoroushAntiSpamBot()

    try:
        await bot.initialize_client()
        await bot.client.connect()

        for cid in [-1000023164149, 23093376]:
            try:
                chat = await bot.client.get_entity(cid)
                print("OK:", cid, chat)
            except Exception as e:
                print("FAIL:", cid, e)

    finally:
        try:
            await bot.client.disconnect()
        except:
            pass

asyncio.run(main())
