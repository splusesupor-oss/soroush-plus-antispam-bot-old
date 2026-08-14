"""Big Spam early detection + immediate cleanup. No network."""
import asyncio
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "splusthon" not in sys.modules:
    fake = types.ModuleType("splusthon")
    fake.Button = object
    fake.types = types.ModuleType("splusthon.types")
    tl = types.ModuleType("splusthon.tl")
    tl_types = types.ModuleType("splusthon.tl.types")

    class _Ent:
        def __init__(self, offset=0, length=0, **_kwargs):
            self.offset = offset
            self.length = length

    tl_types.MessageEntityBold = _Ent
    tl_types.MessageEntityBlockquote = _Ent
    tl.types = tl_types
    tl.functions = types.ModuleType("splusthon.tl.functions")
    fake.tl = tl
    sys.modules["splusthon"] = fake
    sys.modules["splusthon.tl"] = tl
    sys.modules["splusthon.tl.types"] = tl_types
    sys.modules["splusthon.tl.functions"] = tl.functions
    sys.modules["splusthon.types"] = fake.types

from modules import big_spam
from modules.message_delete_queue import MessageDeleteQueue
import handlers.message_handler as handler
from modules import message_tracker


PASSED = FAILED = 0


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


def _rows(*texts, start_id=1, now=None):
    stamp = time.time() if now is None else now
    rows = []
    for offset, text in enumerate(texts):
        rows.append({
            "message_id": start_id + offset,
            "text": text,
            "timestamp": stamp,
        })
    return rows


def test_two_promotional_messages_detect():
    print("\n### دو پیام تبلیغاتی مشابه → تشخیص")
    for text in (
        "بیو چک بیا پیوی",
        "فیلم گذاشتم بیوم",
        "بیو چک",
    ):
        hit, reason, ids = big_spam.detect_big_spam(text, _rows(text, text))
        check(f"{text!r} x2 detected", hit, f"-> {hit} {reason}")
        check(f"{text!r} x2 has both ids", ids == {1, 2}, f"-> {ids}")


def test_single_ordinary_or_single_ad_not_spam():
    print("\n### یک پیام عادی یا یک تبلیغ تنها → تشخیص نشود")
    for text in ("سلام", "خوبی؟", "بیو چک بیا پیوی", "فیلم دیشب عالی بود"):
        hit, reason, ids = big_spam.detect_big_spam(text, _rows(text))
        check(f"single {text!r} ignored", not hit, f"-> {reason} {ids}")
    two_hello = big_spam.detect_big_spam("سلام", _rows("سلام", "سلام"))
    check("دو سلام عادی اسپم نیست", not two_hello[0], f"-> {two_hello}")


def test_packed_phrase_in_one_message():
    print("\n### یک پیام با بیش از ۵ تکرار عبارت تبلیغاتی")
    packed = "بیو چک بیا پیوی\n" * 6
    hit, reason, ids = big_spam.detect_big_spam(packed, _rows(packed))
    check("packed ad box detected", hit, f"-> {reason}")
    check("reason is phrase repeat", reason == "repeated_promotional_phrase")
    many_kheili = " ".join(["خیلی"] * 10)
    miss, _, _ = big_spam.detect_big_spam(many_kheili, _rows(many_kheili))
    check("تکرار یک کلمه عادی اسپم نیست", not miss)


def test_different_ads_are_not_forced_together():
    print("\n### دو تبلیغ نامرتبط در پیام اول/دوم کورکورانه یکی نیستند")
    hit, _, _ = big_spam.detect_big_spam(
        "فیلم گذاشتم بیوم",
        _rows("جوین کانال اسپم", "فیلم گذاشتم بیوم"),
    )
    check("ads with different markers still both promotional",
          big_spam.looks_promotional("فیلم گذاشتم بیوم")
          and big_spam.looks_promotional("جوین کانال اسپم"))
    # They share no marker and are not similar, so 2 different campaigns
    # should not trip the similar-repeat path.
    check("unrelated campaigns are not treated as one wave", not hit)


def test_batch_is_max_not_start_gate():
    print("\n### batch سقف است نه شرط شروع")
    check("1 id → یک دسته", big_spam.chunk_ids([1]) == [[1]])
    check("5 ids → همان ۵ تا", big_spam.chunk_ids([5, 4, 3, 2, 1]) == [[1, 2, 3, 4, 5]])
    check("37 ids → یک دسته", len(big_spam.chunk_ids(range(1, 38))) == 1)
    check("37 ids کامل", big_spam.chunk_ids(range(1, 38))[0] == list(range(1, 38)))
    check("60 ids → یک دسته فوری", big_spam.chunk_ids(range(1, 61)) == [list(range(1, 61))])
    batches_100 = big_spam.chunk_ids(range(1, 101))
    check("100 ids → یک دسته", batches_100 == [list(range(1, 101))])
    batches_300 = big_spam.chunk_ids(range(1, 301))
    check("300 ids → ۳ دسته صدتایی", [len(b) for b in batches_300] == [100, 100, 100])
    huge = list(range(1, 1001))
    batches_1000 = big_spam.chunk_ids(huge)
    flat = [item for batch in batches_1000 for item in batch]
    check("1000 ids هیچکدام گم نشد", flat == huge)
    check("خالی → بدون انتظار", big_spam.chunk_ids([]) == [])
    check("id نامعتبر حذف شد", big_spam.chunk_ids([0, -2, "x", 7]) == [[7]])


def test_drain_five_ids_immediately(monkeypatch=None):
    print("\n### ۵ پیام فوراً پاک می‌شوند")

    async def scenario():
        bot = SimpleNamespace(logger=SimpleNamespace(
            log_info=lambda *_: None, log_error=lambda *_: None
        ), _big_spam_incidents={})
        incident = handler._big_spam_incident(bot, (-1, 2), {1, 2, 3, 4, 5})
        seen = []

        async def fake_cleanup(_bot, _chat, _user, ids):
            seen.append(list(ids))
            return len(ids), []

        async def fake_notice(*_args):
            return True

        handler.cleanup_spam_messages = fake_cleanup
        handler._send_spam_ban_cleanup_notification = fake_notice
        await handler._drain_big_spam_incident(
            bot, SimpleNamespace(sender=None), -1, 2, incident
        )
        return seen, (-1, 2) not in bot._big_spam_incidents

    # restore after
    original_cleanup = handler.cleanup_spam_messages
    original_notice = handler._send_spam_ban_cleanup_notification
    try:
        seen, cleared = asyncio.run(scenario())
    finally:
        handler.cleanup_spam_messages = original_cleanup
        handler._send_spam_ban_cleanup_notification = original_notice
    check("یک فراخوانی با همان ۵ id", seen == [[1, 2, 3, 4, 5]], f"-> {seen}")
    check("incident بعد از cleanup پاک شد", cleared)


def test_drain_three_hundred_is_three_batches():
    print("\n### ۳۰۰ پیام → ۳ batch صدتایی")

    async def scenario():
        bot = SimpleNamespace(logger=SimpleNamespace(
            log_info=lambda *_: None, log_error=lambda *_: None
        ), _big_spam_incidents={})
        seed = set(range(1, 301))
        incident = handler._big_spam_incident(bot, (-3, 9), seed)
        sizes = []

        async def fake_cleanup(_bot, _chat, _user, ids):
            sizes.append(len(list(ids)))
            return len(ids), []

        async def fake_notice(*_args):
            return True

        handler.cleanup_spam_messages = fake_cleanup
        handler._send_spam_ban_cleanup_notification = fake_notice
        await handler._drain_big_spam_incident(
            bot, SimpleNamespace(sender=None), -3, 9, incident
        )
        return sizes

    original_cleanup = handler.cleanup_spam_messages
    original_notice = handler._send_spam_ban_cleanup_notification
    try:
        sizes = asyncio.run(scenario())
    finally:
        handler.cleanup_spam_messages = original_cleanup
        handler._send_spam_ban_cleanup_notification = original_notice
    check("سه دسته ۱۰۰تایی", sizes == [100, 100, 100], f"-> {sizes}")


def test_retry_does_not_drop_or_double_complete():
    print("\n### retry همان id را نگه می‌دارد و دوباره‌کاری موفق را گم نمی‌کند")

    async def scenario():
        bot = SimpleNamespace(logger=SimpleNamespace(
            log_info=lambda *_: None, log_error=lambda *_: None
        ), _big_spam_incidents={})
        incident = handler._big_spam_incident(bot, (-4, 4), {201, 202})
        calls = []

        async def fake_cleanup(_bot, _chat, _user, ids):
            calls.append(tuple(ids))
            if len(calls) == 1:
                return 0, list(ids)
            return len(ids), []

        async def instant(_seconds):
            return None

        async def fake_notice(*_args):
            return True

        handler.cleanup_spam_messages = fake_cleanup
        handler._send_spam_ban_cleanup_notification = fake_notice
        original_sleep = handler._asyncio.sleep
        handler._asyncio.sleep = instant
        try:
            await handler._drain_big_spam_incident(
                bot, SimpleNamespace(sender=None), -4, 4, incident
            )
        finally:
            handler._asyncio.sleep = original_sleep
        return calls, incident["deleted_ids"], (-4, 4) not in bot._big_spam_incidents

    original_cleanup = handler.cleanup_spam_messages
    original_notice = handler._send_spam_ban_cleanup_notification
    try:
        calls, deleted, cleared = asyncio.run(scenario())
    finally:
        handler.cleanup_spam_messages = original_cleanup
        handler._send_spam_ban_cleanup_notification = original_notice
    check("اول fail بعد موفقیت همان idها", calls[0] == calls[1] == (201, 202),
          f"-> {calls}")
    check("هر دو id در deleted", deleted == {201, 202}, f"-> {deleted}")
    check("incident در پایان پاک شد", cleared)


def test_early_ban_starts_cleanup_before_ban_rpc():
    print("\n### ban و cleanup منتظر تمام شدن موج نمی‌مانند")

    async def scenario():
        started = []

        class Queue:
            def enqueue(self, chat_id, action, operation, **kwargs):
                started.append(("ban", chat_id, action))
                return True

        bot = SimpleNamespace(
            logger=SimpleNamespace(log_info=lambda *_: None, log_error=lambda *_: None),
            punished_users=set(),
            moderation_queue=Queue(),
            admin_actions=SimpleNamespace(ban_user=lambda *a, **k: None),
        )
        bot.set_spam_lock = lambda key: None
        bot.clear_spam_lock = lambda key: None
        event = SimpleNamespace(message=SimpleNamespace(id=2))
        started_cleanup = []

        async def fake_drain(_bot, _event, _chat, _user, incident):
            started_cleanup.append(set(incident["ids"]))
            await asyncio.sleep(0)

        original = handler._drain_big_spam_incident
        handler._drain_big_spam_incident = fake_drain
        try:
            ok = handler._queue_big_spam_ban(
                bot, event, -8, 11, None, {1, 2}, "repeated_promotional_messages"
            )
            await asyncio.sleep(0.01)
        finally:
            handler._drain_big_spam_incident = original
        return ok, started, started_cleanup, ( -8, 11) in getattr(bot, "_big_spam_incidents", {})

    ok, started, started_cleanup, incident_present = asyncio.run(scenario())
    check("ban همان لحظه صف شد", started == [("ban", -8, "ban")], f"-> {started}")
    check("cleanup قبل از موفقیت ban شروع شد", started_cleanup == [{1, 2}],
          f"-> {started_cleanup}")
    check("queue_big_spam_ban موفق بود", ok is True)
    check("incident جدا با chat+user ساخته شد", incident_present)


def test_group_b_not_blocked_by_group_a_cleanup():
    print("\n### پاکسازی گروه A دستور گروه B را نگه نمی‌دارد")

    class Client:
        def __init__(self):
            self.order = []
            self.hold = asyncio.Event()
            self.started = asyncio.Event()

        async def delete_messages(self, chat_id, ids):
            if chat_id == -100 and not self.started.is_set():
                self.started.set()
                await self.hold.wait()
            self.order.append((chat_id, list(ids)))

    async def scenario():
        client = Client()
        logger = SimpleNamespace(log_info=lambda *_: None, log_error=lambda *_: None)
        queue = MessageDeleteQueue(client, logger, batch_size=100, inter_batch_delay=0)
        queue.enqueue(-100, list(range(1, 6)), priority=1)
        await client.started.wait()
        other = queue.enqueue(-200, [9], priority=0)
        await asyncio.wait_for(asyncio.wrap_future(other), timeout=0.5)
        finished_first = other.done()
        client.hold.set()
        return finished_first, client.order

    finished_first, order = asyncio.run(scenario())
    check("حذف/دستور گروه B تمام شد در حالی که A هنوز drain می‌شد",
          finished_first, f"-> {order}")


def test_handler_wrapper_uses_tracker():
    print("\n### wrapper هندلر از tracker همان chat استفاده می‌کند")
    message_tracker.reset_all()
    chat_a, chat_b, user = -501, -502, 77
    message_tracker.add_message(chat_a, user, 1, "بیو چک بیا پیوی")
    message_tracker.add_message(chat_a, user, 2, "بیو چک بیا پیوی")
    message_tracker.add_message(chat_b, user, 3, "بیو چک بیا پیوی")
    hit_a, _, ids_a = handler._big_repeated_spam(chat_a, user, "بیو چک بیا پیوی")
    hit_b, _, ids_b = handler._big_repeated_spam(chat_b, user, "بیو چک بیا پیوی")
    check("گروه A با دو پیام تشخیص داده شد", hit_a and ids_a == {1, 2}, f"-> {ids_a}")
    check("گروه B با یک پیام تشخیص نشد", not hit_b, f"-> {ids_b}")
    message_tracker.reset_all()


def main():
    test_two_promotional_messages_detect()
    test_single_ordinary_or_single_ad_not_spam()
    test_packed_phrase_in_one_message()
    test_different_ads_are_not_forced_together()
    test_batch_is_max_not_start_gate()
    test_drain_five_ids_immediately()
    test_drain_three_hundred_is_three_batches()
    test_retry_does_not_drop_or_double_complete()
    test_early_ban_starts_cleanup_before_ban_rpc()
    test_group_b_not_blocked_by_group_a_cleanup()
    test_handler_wrapper_uses_tracker()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
