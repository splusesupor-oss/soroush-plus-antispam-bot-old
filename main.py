from core.bot_working_split_ok import SoroushAntiSpamBot
import asyncio

async def main():
    bot = SoroushAntiSpamBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
