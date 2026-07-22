import time
import asyncio

_old = asyncio.create_task

def create_task(coro, *args, **kwargs):
    async def wrap():
        t = time.perf_counter()
        try:
            return await coro
        finally:
            dt = (time.perf_counter() - t) * 1000
            if dt > 100:
                print(f"[SLOW] {dt:.1f} ms -> {coro}")
    return _old(wrap(), *args, **kwargs)

asyncio.create_task = create_task

import main
asyncio.run(main.main())
