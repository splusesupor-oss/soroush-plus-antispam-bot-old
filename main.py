from core.bot_working_split_ok import SoroushAntiSpamBot
from modules.time_utils import TEHRAN, now_local
import asyncio

async def main():
    # نمایشِ زمانِ واقعیِ تهران در ترمینال هنگام راه‌اندازی، تا مشخص باشد
    # ربات واقعاً با چه زمانی کار می‌کند.
    _now = now_local()
    print(f"[START] Tehran time: {_now.strftime('%Y-%m-%d %H:%M:%S')} "
          f"({TEHRAN})")
    bot = SoroushAntiSpamBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
