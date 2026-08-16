"""Concurrent groups must not share a worker, queue, or lock."""
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.group_dispatch import (
    LANE_CONTROL,
    LANE_NORMAL,
    PRIORITY_ADMIN,
    PRIORITY_COMMAND,
    PRIORITY_NORMAL,
    GroupContext,
    GroupDispatcher,
    worker_lane_for,
)

PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


class Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def log_info(self, message):
        self.infos.append(message)

    def log_error(self, message):
        self.errors.append(message)


def test_each_chat_has_own_context():
    print("\n### هر chat_id یک GroupContext جدا دارد")
    dispatcher = GroupDispatcher(logger=Logger())
    # submit is sync and must not require a running loop just to inspect
    # isolation. Jobs stay queued until a loop starts the workers.
    ok1 = dispatcher.submit(-1, lambda: None, priority=PRIORITY_NORMAL)
    ok2 = dispatcher.submit(-2, lambda: None, priority=PRIORITY_NORMAL)
    check("submit بدون loop کرش نمی‌کند", ok1 and ok2)
    check("دو context", dispatcher.context_count() == 2,
          f"-> {dispatcher.context_count()}")
    check("context type", isinstance(dispatcher._context(-1), GroupContext))
    check("صف‌های دو گروه جدا هستند",
          dispatcher._contexts[-1].queues is not dispatcher._contexts[-2].queues)
    check("admin/command روی worker کنترل می‌روند",
          worker_lane_for(PRIORITY_ADMIN, "admin") == LANE_CONTROL
          and worker_lane_for(PRIORITY_COMMAND, "command") == LANE_CONTROL)
    check("normal روی worker جدا می‌ماند",
          worker_lane_for(PRIORITY_NORMAL, "normal") == LANE_NORMAL)


def test_five_second_group_a_does_not_block_b():
    print("\n### گروه A پنج ثانیه کار می‌کند؛ B و C صبر نمی‌کنند")

    async def scenario():
        dispatcher = GroupDispatcher(max_pending_normal=80, logger=Logger())
        hold_a = asyncio.Event()
        finished = []

        async def slow_a():
            finished.append(("a", "start", time.perf_counter()))
            await hold_a.wait()
            finished.append(("a", "end", time.perf_counter()))

        async def fast(name):
            finished.append((name, "done", time.perf_counter()))

        t0 = time.perf_counter()
        dispatcher.submit(-100, slow_a, priority=PRIORITY_NORMAL, kind="normal")
        await asyncio.sleep(0)
        dispatcher.submit(-200, lambda: fast("b"), priority=PRIORITY_NORMAL, kind="normal")
        dispatcher.submit(-300, lambda: fast("c"), priority=PRIORITY_COMMAND, kind="command")
        await asyncio.sleep(0.08)
        b_done = any(row[0] == "b" for row in finished)
        c_done = any(row[0] == "c" for row in finished)
        a_ended = any(row[0] == "a" and row[1] == "end" for row in finished)
        elapsed = time.perf_counter() - t0
        hold_a.set()
        await dispatcher.join(timeout=1)
        return b_done, c_done, a_ended, elapsed, finished

    b_done, c_done, a_ended, elapsed, finished = asyncio.run(scenario())
    check("B تمام شد در حالی که A هنوز نگه داشته بود", b_done and not a_ended)
    check("C تمام شد در حالی که A هنوز نگه داشته بود", c_done and not a_ended)
    check("انتظار B/C نزدیک صفر است (نه چند ثانیه)",
          elapsed < 0.5, f"-> {elapsed:.3f}s {finished}")


def test_same_group_command_not_behind_normal():
    print("\n### command همان گروه پشت normal سنگین نمی‌ماند")

    async def scenario():
        dispatcher = GroupDispatcher(logger=Logger())
        hold = asyncio.Event()
        order = []

        async def normal():
            order.append("n")
            await hold.wait()

        async def command():
            order.append("cmd")

        dispatcher.submit(7, normal, priority=PRIORITY_NORMAL, kind="normal")
        await asyncio.sleep(0)
        dispatcher.submit(7, command, priority=PRIORITY_COMMAND, kind="command")
        await asyncio.sleep(0.05)
        ok = "cmd" in order and order.index("cmd") > order.index("n")
        hold.set()
        await dispatcher.join(timeout=1)
        return ok, order

    ok, order = asyncio.run(scenario())
    check("command اجرا شد قبل از پایان normal", ok, f"-> {order}")


def test_same_group_admin_not_behind_normal():
    print("\n### moderation همان گروه پشت normal سنگین نمی‌ماند")

    async def scenario():
        dispatcher = GroupDispatcher(logger=Logger())
        hold = asyncio.Event()
        order = []

        async def normal():
            order.append("n")
            await hold.wait()

        async def ban():
            order.append("ban")

        dispatcher.submit(8, normal, priority=PRIORITY_NORMAL, kind="normal")
        await asyncio.sleep(0)
        dispatcher.submit(8, ban, priority=PRIORITY_ADMIN, kind="admin")
        await asyncio.sleep(0.05)
        ok = "ban" in order
        hold.set()
        await dispatcher.join(timeout=1)
        return ok, order

    ok, order = asyncio.run(scenario())
    check("ban اجرا شد در حالی که normal نگه داشته شده", ok, f"-> {order}")


def test_queued_jobs_run_after_loop_starts():
    print("\n### شغل‌های enqueue‌شده بدون loop بعداً اجرا می‌شوند")
    dispatcher = GroupDispatcher(logger=Logger())
    ran = []
    dispatcher.submit(-9, lambda: ran.append("n"), priority=PRIORITY_NORMAL)
    dispatcher.submit(-9, lambda: ran.append("cmd"), priority=PRIORITY_COMMAND)
    check("قبل از loop هنوز اجرا نشده", ran == [])

    async def scenario():
        for ctx in list(dispatcher._contexts.values()):
            for lane, queue in list(ctx.queues.items()):
                dispatcher._ensure_worker(ctx, lane, queue)
        await dispatcher.join(timeout=1)
        return dispatcher.context_count()

    leftover = asyncio.run(scenario())
    check("هر دو شغل بعد از شروع loop اجرا شدند",
          "n" in ran and "cmd" in ran, f"-> {ran}")
    check("بعد از join context آزاد شد", leftover == 0, f"-> {leftover}")


def test_idle_context_released():
    print("\n### context گروه بیکار بعد از اتمام worker آزاد می‌شود")

    async def scenario():
        dispatcher = GroupDispatcher(logger=Logger())
        dispatcher.submit(-44, lambda: None, priority=PRIORITY_NORMAL)
        await dispatcher.join(timeout=1)
        return dispatcher.context_count(), dispatcher.worker_count()

    contexts, workers = asyncio.run(scenario())
    check("context بیکار پاک شد", contexts == 0, f"-> {contexts}")
    check("worker نماند", workers == 0, f"-> {workers}")


if __name__ == "__main__":
    test_each_chat_has_own_context()
    test_five_second_group_a_does_not_block_b()
    test_same_group_command_not_behind_normal()
    test_same_group_admin_not_behind_normal()
    test_queued_jobs_run_after_loop_starts()
    test_idle_context_released()
    print(f"\n{PASSED} passed, {FAILED} failed")
    raise SystemExit(1 if FAILED else 0)
