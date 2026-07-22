import asyncio
from main import SoroushAntiSpamBot

async def main():
    bot = SoroushAntiSpamBot()
    await bot.initialize_client()
    await bot.client.connect()

    print("منتظر پیام فورواردی...")

    @bot.client.on(events.NewMessage())
    async def handler(event):
        msg = event.message

        print("TEXT:", msg.message)
        print("FWD:", msg.fwd_from)

        if msg.fwd_from:
            print("FWD DIR:")
            print(dir(msg.fwd_from))

    await bot.client.run_until_disconnected()

from splusthon import events

asyncio.run(main())
