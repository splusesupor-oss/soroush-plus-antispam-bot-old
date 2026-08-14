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
    packed_word = " ".join(["بمنچه"] * 6)
    hit, reason, ids = big_spam.detect_big_spam(packed_word, _rows(packed_word))
    check("بمنچه بسته‌شده در یک پیام Big Spam است", hit, f"-> {reason}")
    check("packed single-word reason", reason == "repeated_promotional_phrase")
    glued = "بمنچه" * 6
    hit, _, _ = big_spam.detect_big_spam(glued, _rows(glued))
    check("بمنچه بدون فاصله هم intra-message است", hit)


def test_repeated_campaign_without_marker_list():
    print("\n### تکرار یکسان/نزدیک بدون لیست ثابت")
    hit, reason, ids = big_spam.detect_big_spam(
        "بیا گروه فیلم", _rows("بیا گروه فیلم", "بیا گروه فیلم")
    )
    check("بیا گروه فیلم x2 بدون marker", hit, f"-> {reason} {ids}")
    check("هر دو id ثبت شد", ids == {1, 2}, f"-> {ids}")

    hit, _, ids = big_spam.detect_big_spam(
        "تا دیر نشده بکوب نود داریم",
        _rows("تا دیر نشده بکوب نود داریم", "تا دیر نشده بکوب نود داریم"),
    )
    check("بکوب نود x2", hit, f"-> {ids}")

    hit, _, ids = big_spam.detect_big_spam(
        "فالو کن بیا پیوی",
        _rows("فالو کن بیا پیوی", "فالو کن بیا پیوی"),
    )
    check("فالو کن بیا پیوی x2", hit)

    hit, _, ids = big_spam.detect_big_spam(
        "بیا گروه فیلم جدید",
        _rows("بیا گروه فیلم", "بیا گروه فیلم الان", "بیا گروه فیلم جدید"),
    )
    check("تغییر کوچک همان الگوست", hit, f"-> {ids}")
    check("هر سه پیام مشابه در incident", ids == {1, 2, 3}, f"-> {ids}")

    three_hello = big_spam.detect_big_spam(
        "سلام", _rows("سلام", "سلام", "سلام")
    )
    check("سلام x3 هنوز عادی است", not three_hello[0])
    two_short = big_spam.detect_big_spam("خوبی؟", _rows("خوبی؟", "خوبی؟"))
    check("خوبی x2 عادی است", not two_short[0])


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


def test_separate_short_messages_are_not_big_spam():
    print("\n### پیام‌های کوتاه جدا جدا Big Spam نیستند")
    hit, reason, ids = big_spam.detect_big_spam(
        "بمنچه", _rows("بمنچه", "بمنچه", "بمنچه")
    )
    check("بمنچه x3 جدا تشخیص نشود", not hit, f"-> {reason} {ids}")
    hit, _, _ = big_spam.detect_big_spam("بمنچه", _rows("بمنچه", "بمنچه"))
    check("بمنچه x2 جدا تشخیص نشود", not hit)
    ordinary = "فیلم دیشب عالی بود"
    hit, reason, _ = big_spam.detect_big_spam(ordinary, _rows(ordinary, ordinary))
    check("جمله عادی x2 Big Spam نیست", not hit, f"-> {reason}")
    hit, _, _ = big_spam.detect_big_spam(
        ordinary, _rows(ordinary, ordinary, ordinary, ordinary)
    )
    check("جمله عادی x4 هم موج تبلیغاتی نیست", not hit)


def _bio_wave_variant(index):
    stretch_k = "ک" * (1 + index % 6)
    stretch_v = "و" * (1 + index % 4)
    emojis = ["🥺", "🧸", "❤️", "🔥", "✨", "😍", "💋"]
    left, right = emojis[index % 7], emojis[(index + 3) % 7]
    if index % 5 == 0:
        return f"بیوچک{left}بیوچک{stretch_k}{right}"
    if index % 5 == 1:
        return f"بیوچکک{left}بیوچک{stretch_k}{right}"
    if index % 5 == 2:
        return f"بی{stretch_v}چک{left}بیوچک{stretch_k}{right}"
    if index % 5 == 3:
        return f"بیوچک{left}"
    return f"بیو چک {left} بیوچک{stretch_k} {right}"


def test_obfuscated_promotional_wave():
    print("\n### موج تبلیغاتی با ایموجی و حروف کشیده")
    first = _bio_wave_variant(0)
    second = _bio_wave_variant(1)
    check("نرمال‌سازی ایموجی را حذف می‌کند", "🥺" not in big_spam.normalize_text(first))
    check(
        "حروف کشیده به ریشه نزدیک می‌شوند",
        "بیوچک" in big_spam.compact_text("بیوووووچک")
        and "بیوچک" in big_spam.compact_text("بیوچکککک")
        and "بیوچک" in big_spam.compact_text("بیییووچک"),
    )
    check(
        "دو واریانت بعد از normalize تبلیغاتی‌اند",
        big_spam.looks_promotional(first) and big_spam.looks_promotional(second),
    )
    check("واریانت‌ها یک کمپین هستند", big_spam.similar_promotional(first, second))

    wave = [_bio_wave_variant(index) for index in range(50)]
    rows = _rows(*wave)
    hit, reason, ids = big_spam.detect_big_spam(wave[-1], rows)
    check("موج ۵۰تایی تشخیص داده شد", hit, f"-> {reason}")
    check("همه ۵۰ id وارد incident شد", ids == set(range(1, 51)), f"-> {len(ids)} ids")

    early = big_spam.detect_big_spam(wave[1], _rows(wave[0], wave[1]))
    check("از پیام دوم موج قوی شروع می‌شود", early[0], f"-> {early[1]}")
    check("idهای همان لحظه از دست نرفت", early[2] == {1, 2}, f"-> {early[2]}")

    mixed_texts = ["سلام ظهر بخیر"] + wave[:9]
    hit, _, ids = big_spam.detect_big_spam(mixed_texts[-1], _rows(*mixed_texts))
    check(
        "بعد از تشخیص، همه idهای پنجره برمی‌گردد نه فقط match دقیق",
        hit and ids == set(range(1, 11)),
        f"-> {ids}",
    )


def test_normalization_does_not_break_ordinary_chat():
    print("\n### نرمال‌سازی پیام عادی را اسپم نمی‌کند")
    for text in ("سلام🥺", "خوبی؟😍", "ممنون❤️", "صبح بخیر✨"):
        hit, reason, _ = big_spam.detect_big_spam(text, _rows(text, text, text))
        check(f"{text!r} x3 عادی است", not hit, f"-> {reason}")


def test_incident_stays_per_chat_user():
    print("\n### incident فقط (chat_id, user_id) است و cleanup همه idها را می‌گیرد")
    message_tracker.reset_all()
    chat_a, chat_b, user_a, user_b = -701, -702, 11, 12
    wave = [_bio_wave_variant(index) for index in range(8)]
    for index, text in enumerate(wave, 1):
        message_tracker.add_message(chat_a, user_a, index, text)
        message_tracker.add_message(chat_a, user_b, 100 + index, text)
        message_tracker.add_message(chat_b, user_a, 200 + index, text)
    hit_a, _, ids_a = handler._big_repeated_spam(chat_a, user_a, wave[-1])
    hit_other, _, ids_other = handler._big_repeated_spam(chat_a, user_b, wave[-1])
    hit_b, _, ids_b = handler._big_repeated_spam(chat_b, user_a, wave[-1])
    check("کاربر A در گروه A تشخیص داده شد", hit_a, f"-> {ids_a}")
    check("cleanup همان کاربر همان گروه همه idها را دارد", ids_a == set(range(1, 9)), f"-> {ids_a}")
    check("کاربر B در همان گروه جدا است", hit_other and ids_other == set(range(101, 109)), f"-> {ids_other}")
    check("همان کاربر در گروه B قاطی نشد", hit_b and ids_b == set(range(201, 209)), f"-> {ids_b}")
    message_tracker.reset_all()



def test_late_wave_ids_rejoin_after_early_drain():
    print("\n### بعد از trigger روی پیام ۲، idهای ۱ تا ۵۰ از دست نروند")

    async def scenario():
        message_tracker.reset_all()
        chat_id, user_id = -8801, 55
        deleted = []

        class Queue:
            def enqueue(self, chat_id, action, operation, **kwargs):
                return True

        bot = SimpleNamespace(
            logger=SimpleNamespace(log_info=lambda *_: None, log_error=lambda *_: None),
            punished_users=set(),
            spam_lock=set(),
            moderation_queue=Queue(),
            admin_actions=SimpleNamespace(ban_user=lambda *a, **k: None),
        )
        bot.set_spam_lock = lambda key: bot.spam_lock.add(key)
        bot.clear_spam_lock = lambda key: bot.spam_lock.discard(key)
        bot.is_spam_locked = lambda key: key in bot.spam_lock

        async def fake_cleanup(_bot, _chat, _user, ids):
            deleted.append(set(ids))
            return len(ids), []

        async def fake_notice(*_args):
            return True

        async def instant(_seconds):
            return None

        original_cleanup = handler.cleanup_spam_messages
        original_notice = handler._send_spam_ban_cleanup_notification
        original_sleep = handler._asyncio.sleep
        handler.cleanup_spam_messages = fake_cleanup
        handler._send_spam_ban_cleanup_notification = fake_notice
        handler._asyncio.sleep = instant
        try:
            wave = [_bio_wave_variant(index) for index in range(50)]
            event = SimpleNamespace(message=SimpleNamespace(id=2), sender=None)
            for index, text in enumerate(wave[:2], 1):
                handler._capture_big_spam_message(bot, chat_id, user_id, index)
                message_tracker.add_message(chat_id, user_id, index, text)
                hit, reason, ids = handler._big_repeated_spam(chat_id, user_id, text)
                if hit:
                    ids.add(index)
                    handler._queue_big_spam_ban(
                        bot, event, chat_id, user_id, None, ids, reason
                    )
            pending = [
                task for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
            ]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            first_deleted = set().union(*deleted) if deleted else set()
            for index, text in enumerate(wave[2:], 3):
                event = SimpleNamespace(message=SimpleNamespace(id=index), sender=None)
                handler._capture_big_spam_message(bot, chat_id, user_id, index)
                message_tracker.add_message(chat_id, user_id, index, text)
                if bot.is_spam_locked((chat_id, user_id)) and (
                    chat_id, user_id
                ) in getattr(bot, "_big_spam_incidents", {}):
                    continue
                hit, reason, ids = handler._big_repeated_spam(
                    chat_id, user_id, text
                )
                if hit:
                    ids.add(index)
                    handler._queue_big_spam_ban(
                        bot, event, chat_id, user_id, None, ids, reason
                    )
            pending = [
                task for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
            ]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            all_deleted = set().union(*deleted) if deleted else set()
            return first_deleted, all_deleted
        finally:
            handler.cleanup_spam_messages = original_cleanup
            handler._send_spam_ban_cleanup_notification = original_notice
            handler._asyncio.sleep = original_sleep
            message_tracker.reset_all()

    first_deleted, all_deleted = asyncio.run(scenario())
    check("trigger پیام ۲ idهای ۱ و ۲ را دارد", first_deleted == {1, 2}, f"-> {first_deleted}")
    check("cleanup نهایی هر ۵۰ id را دارد", all_deleted == set(range(1, 51)),
          f"-> missing={sorted(set(range(1, 51)) - all_deleted)}")


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
    test_repeated_campaign_without_marker_list()
    test_different_ads_are_not_forced_together()
    test_batch_is_max_not_start_gate()
    test_drain_five_ids_immediately()
    test_drain_three_hundred_is_three_batches()
    test_retry_does_not_drop_or_double_complete()
    test_early_ban_starts_cleanup_before_ban_rpc()
    test_group_b_not_blocked_by_group_a_cleanup()
    test_separate_short_messages_are_not_big_spam()
    test_obfuscated_promotional_wave()
    test_normalization_does_not_break_ordinary_chat()
    test_incident_stays_per_chat_user()
    test_late_wave_ids_rejoin_after_early_drain()
    test_handler_wrapper_uses_tracker()
    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
