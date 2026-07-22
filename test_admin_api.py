import asyncio
from core.bot_working_split_ok import Bot

async def test():
    bot = Bot()

    chat_id = -1000023164149  # این را با آیدی گروه خودت عوض کن

    print("TEST ADMINS")

    try:
        async for x in bot.client.iter_participants(chat_id):
            print(type(x))
            print(dir(x))
            print(x)
            break
    except Exception as e:
        print("ERROR:", e)

asyncio.run(test())
