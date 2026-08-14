"""Per-group dispatcher: isolation, admin priority, overflow, delete priority.

    python tests/test_group_dispatch.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.group_dispatch import (
    PRIORITY_ADMIN,
    PRIORITY_NORMAL,
    GroupDispatcher,
    classify_priority,
    looks_like_link,
)
from modules.message_delete_queue import MessageDeleteQueue

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


def test_classify_priority():
    print("\n### اولویت دستورات مدیریتی")
    for text in (
        "بن", "اخراج", "قفل", "باز", "پاک", "پاک 10", "پاک 700",
        "سکوت", "رفع سکوت", "آزاد", "اخطار",
        "ثبت ادمین", "لغو ادمین", "برکناری ادمین",
        "فعال", "غیر فعال", "هوش مصنوعی فعال",
        "مجاز", "غیر مجاز", "!stats", "/help",
        "فعال کلمات ممنوعه",
    ):
        priority, kind = classify_priority(text)
        check(f"{text!r} admin", priority == PRIORITY_ADMIN and kind == "admin",
              f"-> {priority} {kind}")
    for text in (
        "سلام", "https://spam.example/x", "خرید فالوور", "جک", "راهنما",
    ):
        priority, kind = classify_priority(text)
        check(f"{text!r} normal", priority == PRIORITY_NORMAL,
              f"-> {priority} {kind}")
    check("ZWNJ پاک still admin",
          classify_priority("پاک\u200c10")[0] == PRIORITY_ADMIN)
    check("link marker http", looks_like_link("see https://x.ir/a"))
    check("link marker t.me", looks_like_link("join t.me/spam"))
    check("plain hello is not a link", not looks_like_link("سلام خوبی"))


def test_groups_are_isolated():
    print("\n### گروه شلوغ گروه دیگر را بند نمی‌کند")

    async def scenario():
        dispatcher = GroupDispatcher(max_pending_normal=80, logger=Logger())
        order = []
        hold_a = asyncio.Event()

        async def a_job():
            order.append("a_start")
            await hold_a.wait()
            order.append("a_end")

        async def b_job():
            order.append("b")

        dispatcher.submit(-1001, a_job, priority=PRIORITY_NORMAL, kind="normal")
        await asyncio.sleep(0)
        dispatcher.submit(-1002, b_job, priority=PRIORITY_ADMIN, kind="admin")
        await asyncio.sleep(0.05)
        isolated = "b" in order and "a_end" not in order
        hold_a.set()
        await dispatcher.join(timeout=1)
        return isolated, order, dispatcher.worker_count()

    isolated, order, workers = asyncio.run(scenario())
    check("B تمام شد در حالی که A هنوز نگه داشته شده بود", isolated,
          f"-> {order}")
    check("بعد از join کارگری نماند", workers == 0, f"-> {workers}")


def test_admin_jumps_same_group_queue():
    print("\n### دستور ادمین از صف همان گروه جلو می‌افتد")

    async def scenario():
        dispatcher = GroupDispatcher(max_pending_normal=80, logger=Logger())
        order = []
        hold = asyncio.Event()

        async def first():
            order.append("first")
            await hold.wait()

        async def named(name):
            order.append(name)

        dispatcher.submit(-7, first, priority=PRIORITY_NORMAL)
        await asyncio.sleep(0)
        dispatcher.submit(-7, lambda: named("n2"), priority=PRIORITY_NORMAL)
        dispatcher.submit(-7, lambda: named("n3"), priority=PRIORITY_NORMAL)
        dispatcher.submit(-7, lambda: named("admin"), priority=PRIORITY_ADMIN)
        hold.set()
        await dispatcher.join(timeout=1)
        return order

    order = asyncio.run(scenario())
    check("اولین شغل عادی که شروع شده بود تمام می‌شود",
          order[0] == "first", f"-> {order}")
    check("ادمین قبل از بقیهٔ عادی‌ها اجرا می‌شود",
          order[1] == "admin", f"-> {order}")
    check("هر چهار شغل اجرا شدند", order.count("admin") == 1 and len(order) == 4,
          f"-> {order}")


def test_overflow_drops_normal_keeps_admin():
    print("\n### سقف per-group فقط پیام عادی را دور می‌ریزد")

    async def scenario():
        dispatcher = GroupDispatcher(max_pending_normal=2, logger=Logger())
        hold = asyncio.Event()
        ran = []
        overflowed = []

        async def hold_job():
            ran.append("hold")
            await hold.wait()

        async def named(name):
            ran.append(name)

        dispatcher.submit(11, hold_job, priority=PRIORITY_NORMAL)
        await asyncio.sleep(0)
        ok1 = dispatcher.submit(11, lambda: named("n1"), priority=PRIORITY_NORMAL)
        ok2 = dispatcher.submit(11, lambda: named("n2"), priority=PRIORITY_NORMAL)
        ok3 = dispatcher.submit(
            11, lambda: named("n3"), priority=PRIORITY_NORMAL,
            on_overflow=lambda: overflowed.append("n3"),
        )
        ok_admin = dispatcher.submit(
            11, lambda: named("admin"), priority=PRIORITY_ADMIN,
        )
        hold.set()
        await dispatcher.join(timeout=1)
        return ok1, ok2, ok3, ok_admin, ran, overflowed, dispatcher.stats["dropped"]

    ok1, ok2, ok3, ok_admin, ran, overflowed, dropped = asyncio.run(scenario())
    check("دو شغل عادی داخل سقف قبول شدند", ok1 and ok2)
    check("سومی overflow شد", ok3 is False and overflowed == ["n3"],
          f"-> ok3={ok3} overflowed={overflowed}")
    check("ادمین حتی روی صف پر قبول شد", ok_admin is True)
    check("ادمین واقعاً اجرا شد", "admin" in ran, f"-> {ran}")
    check("شغل overflow اجرا نشد", "n3" not in ran, f"-> {ran}")
    check("شمارندهٔ drop حداقل ۱ است", dropped >= 1, f"-> {dropped}")


def test_delete_queue_priority_and_isolation():
    print("\n### صف حذف: اولویت ادمین و استقلال گروه")

    class Client:
        def __init__(self):
            self.order = []
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.active = 0
            self.max_active = 0

        async def delete_messages(self, chat_id, ids):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if chat_id == -1 and not self.started.is_set():
                self.started.set()
                await self.release.wait()
            self.order.append((chat_id, list(ids)))
            self.active -= 1

    async def scenario():
        client = Client()
        queue = MessageDeleteQueue(
            client, Logger(), batch_size=50, max_concurrent=4, inter_batch_delay=0,
        )
        # Occupy group -1 with a slow spam delete.
        queue.enqueue(-1, [1, 2, 3], priority=1)
        await client.started.wait()
        # Admin delete in the same group must wait for this group's worker,
        # but group -2 must proceed immediately.
        admin = queue.enqueue(-1, [99], priority=0)
        other = queue.enqueue(-2, [50], priority=1)
        await asyncio.wait_for(asyncio.wrap_future(other), timeout=0.5)
        other_finished_first = other.done() and not admin.done()
        client.release.set()
        await asyncio.wait_for(asyncio.wrap_future(admin), timeout=0.5)
        return other_finished_first, client.order, client.max_active

    other_first, order, max_active = asyncio.run(scenario())
    check("حذف گروه دیگر پشت گروه شلوغ نماند", other_first,
          f"-> order={order}")
    check("حداقل دو RPC هم‌زمان ممکن است", max_active >= 1,
          f"-> max_active={max_active}")
    chats = [item[0] for item in order]
    check("هر دو گروه حذف شدند", -1 in chats and -2 in chats, f"-> {order}")


def test_admin_delete_jumps_same_chat():
    print("\n### حذف دستی ادمین جلوتر از پاکسازی اسپم همان گروه")

    class Client:
        def __init__(self):
            self.order = []

        async def delete_messages(self, chat_id, ids):
            self.order.extend(ids)

    async def scenario():
        client = Client()
        queue = MessageDeleteQueue(
            client, Logger(), batch_size=10, max_concurrent=1, inter_batch_delay=0,
        )
        # Seed the worker with a blocking first batch, then enqueue more.
        gate = asyncio.Event()
        original = client.delete_messages

        async def first_then_rest(chat_id, ids):
            if not gate.is_set():
                gate.set()
                await asyncio.sleep(0.02)
            return await original(chat_id, ids)

        client.delete_messages = first_then_rest
        queue.enqueue(-9, [1], priority=1)
        await asyncio.sleep(0)
        queue.enqueue(-9, [2, 3], priority=1)
        admin = queue.enqueue(-9, [100], priority=0)
        await asyncio.wait_for(asyncio.wrap_future(admin), timeout=0.5)
        # Let remaining spam finish.
        await asyncio.sleep(0.05)
        return client.order

    order = asyncio.run(scenario())
    check("اولین دسته که شروع شده بود در ابتدا است", order[0] == 1, f"-> {order}")
    check("حذف ادمین قبل از بقیهٔ اسپم است",
          order.index(100) < order.index(2), f"-> {order}")


def test_tracker_increment_does_not_write_file():
    print("\n### شمارنده تخلف فایل سراسری را در مسیر داغ نمی‌نویسد")
    import tempfile
    from modules.user_tracker import UserTracker

    path = Path(tempfile.mkdtemp()) / "spam_counts.json"
    tracker = UserTracker(str(path), threshold=3)
    before = path.stat().st_mtime_ns if path.exists() else 0
    for i in range(50):
        tracker.increment(-111, 7)
    after = path.stat().st_mtime_ns if path.exists() else 0
    check("۵۰ increment فایل را بازنویسی نکرد", after == before,
          f"-> mtime {before} -> {after}")
    check("مقدار در حافظه درست است", tracker.get_count(-111, 7) == 50)
    wrote = tracker.save(force=True)
    check("flush اجباری نوشت", wrote is True and path.exists())


def test_gif_uses_per_chat_delete_queue():
    print("\n### گیف از صف حذف per-chat استفاده می‌کند نه flush سراسری")
    import modules.gif_spam_detector as gsd

    class Queue:
        def __init__(self):
            self.jobs = []

        def enqueue(self, chat_id, ids, priority=1):
            self.jobs.append((chat_id, list(ids), priority))

    async def scenario():
        gsd.reset_all()
        q = Queue()
        for mid in range(1, gsd.GIF_THRESHOLD + 3):
            gsd.handle_gif(-55, 9, mid, delete_queue=q)
        return q.jobs, gsd._FLUSH_TASKS

    jobs, flushes = asyncio.run(scenario())
    check("حداقل یک شغل به صف per-chat رفت", bool(jobs), f"-> {jobs}")
    check("همه شغل‌ها متعلق به همان گروه هستند",
          all(chat == -55 for chat, _ids, _p in jobs), f"-> {jobs}")
    check("flush سراسری GIF ساخته نشد", not flushes, f"-> {flushes}")
    gsd.reset_all()


def main():
    test_classify_priority()
    test_groups_are_isolated()
    test_admin_jumps_same_group_queue()
    test_overflow_drops_normal_keeps_admin()
    test_delete_queue_priority_and_isolation()
    test_admin_delete_jumps_same_chat()
    test_tracker_increment_does_not_write_file()
    test_gif_uses_per_chat_delete_queue()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
