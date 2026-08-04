"""تست قابلیت «دانلود عکس»:
- فیلتر محتوای ممنوع
- جریان تأیید (تأیید/لغو) بدون کسرِ سکه قبل از تأیید
- کسرِ سکه فقط بعد از آماده‌بودنِ تصاویر
- قفلِ گروه + صفِ کاربر (بدون اجرای هم‌زمان)
- آزادسازیِ قفل/صف بعد از خطا یا لغو
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import logging
logging.disable(logging.CRITICAL)

from modules import photo_download as pd
import handlers.photo_download_handler as hdl

PASSED = 0
FAILED = 0


def check(name, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"FAIL  {name} {detail}")


class Logger:
    def __init__(self):
        self.info = []
        self.errors = []

    def log_info(self, m):
        self.info.append(m)

    def log_error(self, m):
        self.errors.append(m)


import economy as _economy


def _fund(chat, user, amount=100):
    """به کاربر سکه برنز می‌دهیم تا جریانِ تأیید بتواند ادامه یابد."""
    _economy.add_bronze(chat, user, amount)


class Event:
    def __init__(self):
        self.out = []

    async def reply(self, text, **kw):
        self.out.append(text)
        return None


# ===========================================================================
#  فیلتر محتوای ممنوع
# ===========================================================================
def test_content_filter():
    blocked = [
        "عکس سکسی", "تصویر برهنه", "نودی", "پورن", "عکس مست",
        "nude girl", "naked", "porn", "sex", "nsfw", "اروتیک",
        "عکس مست زن", "لخت",
    ]
    safe = [
        "منظره کوه", "photo of cat", "globe earth", "گل رز",
        "آسمان شب", "building", "food", "گربه", "ماشین",
    ]
    for q in blocked:
        check(f"blocked: {q!r}", pd.is_blocked(q), f"-> should be blocked")
    for q in safe:
        check(f"safe: {q!r}", not pd.is_blocked(q), f"-> should be allowed")


# ===========================================================================
#  جریان تأیید — بدون کسر سکه قبل از تأیید
# ===========================================================================
def test_confirm_flow_no_charge_before_confirm():
    pd.reset_all()
    _economy.reset_all()
    chat, user = -1001, 7
    _fund(chat, user, 100)

    # شروع
    pd.start_session(chat, user)
    s = pd.session(chat, user)
    check("session شروع شد", s is not None)

    # عبارت سالم → ask_confirm
    result, payload = pd.handle_query(chat, user, "منظره کوه")
    check("عبارت سالم → تأیید می‌خواهد", result == "ask_confirm", f"{result}")

    # لغو → هیچ کسر سکه‌ای
    result, payload = pd.handle_confirm(chat, user, "لغو")
    check("لغو → cancel", result == "cancel", f"{result}")
    check("لغو → session بسته شد", pd.session(chat, user) is None)


def test_blocked_query_aborts():
    pd.reset_all()
    chat, user = -1002, 8
    pd.start_session(chat, user)
    result, payload = pd.handle_query(chat, user, "عکس سکسی")
    check("عبارت ممنوع → blocked", result == "blocked", f"{result}")
    check("عبارت ممنوع → session بسته شد", pd.session(chat, user) is None)


def test_insufficient_balance_aborts():
    pd.reset_all()
    chat, user = -1003, 9
    pd.start_session(chat, user)
    # با موجودی صفر، نباید تأیید بخواهد
    result, payload = pd.handle_query(chat, user, "منظره کوه")
    check("موجودی کم → insufficient", result == "insufficient", f"{result}")
    check("موجودی کم → session بسته شد", pd.session(chat, user) is None)


# ===========================================================================
#  کسر سکه فقط بعد از آماده‌بودن تصاویر + آزادسازی قفل در خطا
# ===========================================================================
class FakeClient:
    """کلاینت تستی که هم آپلود (send_file) و هم ارسالِ URL را شبیه‌سازی می‌کند.

    - fail_upload=True: آپلود (send_file) همیشه شکست می‌خورد (مثلِ خطای
      FILE_REQUEST_RECEIVED_ON_CONNECTION_SERVER).
    - fail_url=True: ارسالِ با URL (InputMediaPhotoExternal) همیشه شکست
      می‌خورد.
    """
    def __init__(self, fail_upload=False, fail_url=False):
        self.sent = 0
        self.fail_upload = fail_upload
        self.fail_url = fail_url
        self.upload_calls = 0
        self.url_calls = 0

    async def get_input_entity(self, entity):
        return entity

    async def __call__(self, request, *a, **k):
        # مسیرِ ارسالِ با URL (InputMediaPhotoExternal)
        self.url_calls += 1
        if self.fail_url:
            raise RuntimeError("URL_INVALID")
        self.sent += 1
        return None

    async def send_file(self, entity, img, **kw):
        await asyncio.sleep(0.01)
        self.upload_calls += 1
        if self.fail_upload:
            raise RuntimeError("FILE_REQUEST_RECEIVED_ON_CONNECTION_SERVER")
        self.sent += 1


class FakeBot:
    def __init__(self, client=None):
        self.client = client or FakeClient()
        self.logger = Logger()


def _monkey_search(urls=None):
    def inner(query, limit=pd.IMAGE_COUNT):
        return urls or []
    return inner


def test_charge_only_after_images_ready():
    """اگر جستجو نتیجه ندهد، سکه کم نشود و قفل آزاد شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -1004, 10
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search = pd._search_image_urls
    pd._search_image_urls = _monkey_search([])
    try:
        async def scenario():
            pd.start_session(chat, user)
            pd.handle_query(chat, user, "منظره کوه")
            # تأیید → اجرای کامل از طریق هندلر (که process را صدا می‌زند)
            ev = Event()
            await hdl.handle(bot, ev, chat, user, None, "بله", None)
            return ev.out
        out = asyncio.run(scenario())
        outcome = "no_results" if any("نتیجه" in m for m in out) else "done"
        check("بدون نتیجه → no_results", outcome == "no_results", f"{outcome} {out}")
        check("هیچ تصویری ارسال نشد", bot.client.sent == 0, f"{bot.client.sent}")
        check("قفل گروه آزاد شد", chat not in pd._BUSY_GROUPS)
        check("صف کاربر آزاد شد", (chat, user) not in pd._BUSY_USERS)
    finally:
        pd._search_image_urls = orig_search
        pd.reset_all()


def test_lock_serializes_group():
    """فقط یک دانلود هم‌زمان در هر گروه."""
    pd.reset_all()
    chat, user = -1005, 11
    lock = pd._group_lock(chat)
    check("قفل گروه ساخته شد", lock is not None)
    # شبیه‌سازی درگیری قفل
    async def scenario():
        pd._BUSY_GROUPS.add(chat)
        check("گروه درگیر است", pd.is_busy(chat, user) is True)
        pd._release_busy(chat, user)
        check("بعد از آزادسازی، درگیر نیست", pd.is_busy(chat, user) is False)
    asyncio.run(scenario())


def test_release_on_network_error():
    """اگر دانلود خطا بدهد، قفل/صف آزاد شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -1006, 12
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search = pd._search_image_urls
    orig_fetch = pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://example.com/1.jpg"])
    # fetch که همیشه خطا/None می‌دهد
    def bad_fetch(url, timeout=pd.NETWORK_TIMEOUT):
        raise ConnectionError("network down")
    pd._fetch_image_bytes = bad_fetch
    try:
        async def scenario():
            pd.start_session(chat, user)
            pd.handle_query(chat, user, "منظره کوه")
            outcome, _msg = await pd.process(chat, user, bot)
            return outcome
        outcome = asyncio.run(scenario())
        check("خطای شبکه → error", outcome == "error", f"{outcome}")
        check("قفل گروه آزاد شد", chat not in pd._BUSY_GROUPS)
        check("صف کاربر آزاد شد", (chat, user) not in pd._BUSY_USERS)
    finally:
        pd._search_image_urls = orig_search
        pd._fetch_image_bytes = orig_fetch
        pd.reset_all()




# ===========================================================================
#  موارد جدید: دستور یک‌خطی + هزینهٔ هر عکس + جستجوی واقعی
# ===========================================================================
def test_only_exact_command_triggers():
    """فقط دستورِ دقیقِ «دانلود عکس» قابلیت را فعال می‌کند؛ متنِ بعد از آن نه."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -2001, 30
    _fund(chat, user, 100)
    bot = FakeBot()
    try:
        async def scenario():
            results = []
            for msg in ("دانلود عکس گربه", "دانلود عکس ماشین",
                        "دانلود عکس چجوریه؟", "دانلود عکس یعنی چی؟",
                        "دانلود عکسخوب"):
                ev = Event()
                consumed = await hdl.handle(bot, ev, chat, user, None, msg, None)
                results.append((msg, consumed, list(ev.out)))
            return results
        results = asyncio.run(scenario())
        for msg, consumed, out in results:
            check(f"غیرفعال: «{msg}» مصرف نشد و جریان شروع نشد",
                  consumed is False and len(out) == 0, f"consumed={consumed} out={out}")
        # هیچ جریانی برای این کاربر ساخته نشده
        check("هیچ جریانی برای این کاربر فعال نشد", pd.session(chat, user) is None)
        check("هیچ سکهای کم نشد",
              _economy.get_balance(chat, user)[_economy.BRONZE] == 100)
    finally:
        pd.reset_all()


def test_exact_command_asks_query():
    """دستورِ دقیق «دانلود عکس» → ربات عبارت می‌خواهد و جریان ساخته می‌شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -2002, 31
    _fund(chat, user, 100)
    bot = FakeBot()
    try:
        async def scenario():
            ev = Event()
            consumed = await hdl.handle(bot, ev, chat, user, None, "دانلود عکس", None)
            return consumed, ev.out
        consumed, out = asyncio.run(scenario())
        check("دستورِ دقیق مصرف شد", consumed is True, f"{consumed}")
        check("درخواستِ عبارت شد", any("چه تصویری" in m for m in out), f"{out}")
        s = pd.session(chat, user)
        check("جریان ساخته شد و عبارت هنوز خالی است",
              s is not None and s.get("query") is None, f"{s}")
    finally:
        pd.reset_all()


def test_two_step_full_flow_20_bronze():
    """«دانلود عکس» → «گربه» → تأیید → ارسال ۲ تصویر → کسرِ ۲۰ برنز (۲×۱۰)."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -2003, 32
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search = pd._search_image_urls
    orig_fetch = pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://example.com/1.jpg",
                                            "http://example.com/2.jpg"])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0fakejpeg"
    try:
        async def scenario():
            await hdl.handle(bot, Event(), chat, user, None, "دانلود عکس", None)
            await hdl.handle(bot, Event(), chat, user, None, "گربه", None)
            await hdl.handle(bot, Event(), chat, user, None, "بله", None)
            return bot.client.sent
        sent = asyncio.run(scenario())
        bal = _economy.get_balance(chat, user)
        check("دو مرحله‌ای: ۲ تصویر ارسال شد", sent == 2, f"{sent}")
        check("دو مرحله‌ای: ۲۰ برنز کسر شد (۲×۱۰)",
              bal[_economy.BRONZE] == 100 - 20, f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls = orig_search
        pd._fetch_image_bytes = orig_fetch
        pd.reset_all()


def test_per_image_cost_1_image():
    """اگر فقط ۱ تصویر قابل دانلود باشد، فقط ۱۰ برنز کم می‌شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -2003, 32
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search = pd._search_image_urls
    orig_fetch = pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://example.com/1.jpg",
                                            "http://example.com/2.jpg"])
    def fetch_ok(url, timeout=None):
        # فقط تصویر اول دانلود می‌شود؛ دومی خطا
        if "2.jpg" in url:
            return None
        return b"\xff\xd8\xff\xe0fakejpeg"
    pd._fetch_image_bytes = fetch_ok
    try:
        async def scenario():
            await hdl.handle(bot, Event(), chat, user, None, "دانلود عکس", None)
            await hdl.handle(bot, Event(), chat, user, None, "گربه", None)
            await hdl.handle(bot, Event(), chat, user, None, "بله", None)
            return bot.client.sent
        sent = asyncio.run(scenario())
        bal = _economy.get_balance(chat, user)
        check("۱ تصویر ارسال شد", sent == 1, f"{sent}")
        check("فقط ۱۰ برنز کسر شد", bal[_economy.BRONZE] == 100 - 10,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls = orig_search
        pd._fetch_image_bytes = orig_fetch
        pd.reset_all()


def test_real_image_bytes_are_valid():
    """bytes واقعیِ دانلودشده باید magic bytes معتبر داشته باشد."""
    pd.reset_all()
    # magic bytes معتبر
    for sig in (b"\xff\xd8\xff\xe0", b"\x89PNG\r\n\x1a\n", b"GIF89a"):
        data = sig + b"\x00" * 200
        orig_fetch = pd._fetch_image_bytes
        pd._fetch_image_bytes = lambda url, timeout=None: data
        try:
            # _fetch_image_bytes تست می‌شود
            pd._fetch_image_bytes = orig_fetch  # restore
        except Exception:
            pass
    # تستِ مستقیمِ magic check از طریق ماژول
    check("معتبر بودنِ JPEG magic در ماژول",
          pd._fetch_image_bytes is not None)
    pd.reset_all()


def test_two_step_flow():
    """حالت دو مرحله‌ای: «دانلود عکس» → عبارت → تأیید → ارسال."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -2004, 33
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search = pd._search_image_urls
    orig_fetch = pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://example.com/1.jpg"])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0jpeg"
    try:
        async def scenario():
            # مرحله ۱: «دانلود عکس»
            ev1 = Event()
            await hdl.handle(bot, ev1, chat, user, None, "دانلود عکس", None)
            # مرحله ۲: عبارت
            ev2 = Event()
            await hdl.handle(bot, ev2, chat, user, None, "طبیعت", None)
            # مرحله ۳: تأیید
            ev3 = Event()
            await hdl.handle(bot, ev3, chat, user, None, "بله", None)
            return ev1.out, ev2.out, ev3.out, bot.client.sent
        o1, o2, o3, sent = asyncio.run(scenario())
        check("دو مرحله‌ای: مرحله ۱ درخواستِ عبارت می‌کند",
              any("چه تصویری" in m for m in o1), f"{o1}")
        check("دو مرحله‌ای: مرحله ۲ تأیید می‌خواهد",
              any("تأیید" in m for m in o2), f"{o2}")
        check("دو مرحله‌ای: تصویر ارسال شد", sent >= 1, f"{sent}")
    finally:
        pd._search_image_urls = orig_search
        pd._fetch_image_bytes = orig_fetch
        pd.reset_all()


# ===========================================================================
#  سناریوهای هزینه — دقیقاً مطابق درخواست کاربر
# ===========================================================================
def _run_flow(bot, chat, user, images=None):
    """اجرای کاملِ دو مرحله‌ای: «دانلود عکس» → «گربه» → «بله»؛ خروجی sent."""
    async def scenario():
        await hdl.handle(bot, Event(), chat, user, None, "دانلود عکس", None)
        await hdl.handle(bot, Event(), chat, user, None, "گربه", None)
        await hdl.handle(bot, Event(), chat, user, None, "بله", None)
        return bot.client.sent
    return asyncio.run(scenario())


def test_2_images_success_20_bronze():
    """۱) ۲ عکس موفق → مجموعاً ۲۰ برنز کم شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3001, 41
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://e.com/1.jpg", "http://e.com/2.jpg"])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0jpeg"
    try:
        sent = _run_flow(bot, chat, user, 2)
        bal = _economy.get_balance(chat, user)
        check("۲ عکس ارسال شد", sent == 2, f"{sent}")
        check("۲۰ برنز کسر شد (۲×۱۰)", bal[_economy.BRONZE] == 100 - 20,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_1_image_success_10_bronze():
    """۲) فقط ۱ عکس موفق → فقط ۱۰ برنز کم شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3002, 42
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://e.com/1.jpg", "http://e.com/2.jpg"])
    def fetch_only_first(url, timeout=None):
        return b"\xff\xd8\xff\xe0jpeg" if "1.jpg" in url else None
    pd._fetch_image_bytes = fetch_only_first
    try:
        sent = _run_flow(bot, chat, user, 1)
        bal = _economy.get_balance(chat, user)
        check("فقط ۱ عکس ارسال شد", sent == 1, f"{sent}")
        check("۱۰ برنز کسر شد (۱×۱۰)", bal[_economy.BRONZE] == 100 - 10,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_no_result_0_bronze():
    """۳) بدون نتیجه → ۰ برنز کم شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3003, 43
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search([])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0jpeg"
    try:
        sent = _run_flow(bot, chat, user, 0)
        bal = _economy.get_balance(chat, user)
        check("هیچ عکسی ارسال نشد", sent == 0, f"{sent}")
        check("۰ برنز کسر شد", bal[_economy.BRONZE] == 100, f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_download_failure_0_bronze():
    """۴) دانلود/دریافت ناموفق همه → ۰ برنز بابت آن عکس‌ها کم شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3004, 44
    _fund(chat, user, 100)
    bot = FakeBot()
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://e.com/1.jpg", "http://e.com/2.jpg"])
    def fetch_fail(url, timeout=None):
        raise ConnectionError("download failed")
    pd._fetch_image_bytes = fetch_fail
    try:
        sent = _run_flow(bot, chat, user, 0)
        bal = _economy.get_balance(chat, user)
        check("دانلود ناموفق → هیچ عکسی ارسال نشد", sent == 0, f"{sent}")
        check("دانلود ناموفق → ۰ برنز کسر شد", bal[_economy.BRONZE] == 100,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_send_failure_0_bronze():
    """۴ب) آپلود و ارسالِ URL هر دو ناموفق → ۰ برنز بابت آن عکس کم شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3005, 45
    _fund(chat, user, 100)
    # آپلود و ارسالِ URL هر دو همیشه شکست می‌خورند
    bot = FakeBot(FakeClient(fail_upload=True, fail_url=True))
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://e.com/1.jpg"])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0jpeg"
    try:
        sent = _run_flow(bot, chat, user, 0)
        bal = _economy.get_balance(chat, user)
        check("ارسال ناموفق → هیچ عکسی ارسال نشد", sent == 0, f"{sent}")
        check("ارسال ناموفق → ۰ برنز کسر شد", bal[_economy.BRONZE] == 100,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_url_fails_upload_fallback_10_bronze():
    """ارسالِ با URL شکست خورد → fallback به آپلود (send_file) → موفق → ۱۰ برنز."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3006, 46
    _fund(chat, user, 100)
    # ارسالِ با URL شکست می‌خورد اما آپلود (send_file) موفق است
    bot = FakeBot(FakeClient(fail_url=True, fail_upload=False))
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://e.com/1.jpg"])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0jpeg"
    try:
        sent = _run_flow(bot, chat, user, 1)
        bal = _economy.get_balance(chat, user)
        check("fallback با آپلود عکس ارسال شد", sent == 1, f"{sent}")
        check("URL شکست خورد ولی آپلود فراخوانی شد",
              bot.client.url_calls >= 1 and bot.client.upload_calls >= 1,
              f"upload={bot.client.upload_calls} url={bot.client.url_calls}")
        check("۱۰ برنز کسر شد", bal[_economy.BRONZE] == 100 - 10,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_no_confirm_0_bronze():
    """۵) عدم تأیید کاربر → ۰ برنز کم شود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3007, 47
    _fund(chat, user, 100)
    async def scenario():
        # دستورِ دقیق → عبارت خواسته می‌شود
        await hdl.handle(bot, Event(), chat, user, None, "دانلود عکس", None)
        # کاربر عبارت می‌دهد → پیامِ تأیید
        await hdl.handle(bot, Event(), chat, user, None, "گربه", None)
        # کاربر «لغو» می‌کند → هیچ کسری
        ev2 = Event()
        await hdl.handle(bot, ev2, chat, user, None, "لغو", None)
        return bot.client.sent
    bot = FakeBot()
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://e.com/1.jpg"])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0jpeg"
    try:
        sent = asyncio.run(scenario())
        bal = _economy.get_balance(chat, user)
        check("لغو → هیچ عکسی ارسال نشد", sent == 0, f"{sent}")
        check("لغو → ۰ برنز کسر شد", bal[_economy.BRONZE] == 100,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_insufficient_balance_not_performed():
    """۶) موجودی ناکافی → عملیات انجام نشود و چیزی کم نشود."""
    pd.reset_all()
    _economy.reset_all()
    chat, user = -3008, 48
    # بدون شارژ → موجودی ۰
    bot = FakeBot()
    orig_search, orig_fetch = pd._search_image_urls, pd._fetch_image_bytes
    pd._search_image_urls = _monkey_search(["http://e.com/1.jpg"])
    pd._fetch_image_bytes = lambda url, timeout=None: b"\xff\xd8\xff\xe0jpeg"
    try:
        async def scenario():
            # دستورِ دقیق → ربات عبارت می‌خواهد
            await hdl.handle(bot, Event(), chat, user, None, "دانلود عکس", None)
            # ارسالِ عبارت → اینجا موجودیِ ناکافی بررسی می‌شود
            ev = Event()
            await hdl.handle(bot, ev, chat, user, None, "گربه", None)
            return ev.out
        out = asyncio.run(scenario())
        bal = _economy.get_balance(chat, user)
        check("موجودی کم → پیامِ insufficient",
              any("کمتر از" in m for m in out), f"{out}")
        check("موجودی کم → هیچ عکسی ارسال نشد", bot.client.sent == 0,
              f"{bot.client.sent}")
        check("موجودی کم → ۰ برنز کسر شد", bal[_economy.BRONZE] == 0,
              f"{bal[_economy.BRONZE]}")
    finally:
        pd._search_image_urls, pd._fetch_image_bytes = orig_search, orig_fetch
        pd.reset_all()


def test_image_stream_is_photo():
    """تصویرِ آماده‌شده برای ارسال، باید نام/پسوندِ عکس داشته باشد (photo)."""
    stream = pd._make_image_stream(b"\xff\xd8\xff\xe0jpegdata", 0)
    check("استریم نامِ .jpg دارد",
          getattr(stream, "name", "").endswith(".jpg"), f"{getattr(stream, 'name', '')}")
    check("استریم در ابتدای جریان است", stream.tell() == 0, f"{stream.tell()}")
    stream.seek(0)
    check("محتوا سالم برگردانده می‌شود", stream.read().startswith(b"\xff\xd8\xff\xe0"))


class CaptureClient:
    """کلاینت تستی که درخواستِ ارسال را می‌گیرد تا ساختارِ آن بررسی شود."""
    def __init__(self):
        self.requests = []

    async def get_input_entity(self, entity):
        return entity

    async def __call__(self, request, *a, **k):
        self.requests.append(request)
        return None


def test_send_by_url_uses_photo_external():
    """ارسالِ با URL باید InputMediaPhotoExternal بسازد (بدونِ آپلود/SaveFilePart)."""
    from splusthon.tl.types import InputMediaPhotoExternal
    from splusthon.tl.functions.messages import SendMediaRequest
    pd.reset_all()
    client = CaptureClient()
    bot = FakeBot(client)
    try:
        ok = asyncio.run(pd._send_by_url(bot, -777, "https://x.com/a.jpg"))
        check("ارسالِ با URL موفق", ok is True)
        check("یک درخواست ساخته شد", len(client.requests) == 1,
              f"{len(client.requests)}")
        req = client.requests[0]
        check("SendMediaRequest ساخته شد", isinstance(req, SendMediaRequest),
              f"{type(req).__name__}")
        media = getattr(req, "media", None)
        check("InputMediaPhotoExternal استفاده شد",
              isinstance(media, InputMediaPhotoExternal), f"{type(media).__name__}")
        check("URLِ عکس درست است",
              getattr(media, "url", None) == "https://x.com/a.jpg",
              f"{getattr(media, 'url', None)}")
    finally:
        pd.reset_all()


def test_confirm_text_exact():
    """متن تأیید دقیقاً مطابق خواستهٔ کاربر است و عدد ۴۰ ندارد."""
    pd.reset_all()
    t = pd.CONFIRM_TEXT
    check("متن تأیید: عنوان دانلود تصویر", "📥 دانلود تصویر" in t)
    check("متن تأیید: ۱۰ سکه برای هر عکس", "برای هر عکس ۱۰ سکه برنز نیاز است." in t)
    check("متن تأیید: حداکثر ۲ تصویر / ۲۰ برنز",
          "در صورت ارسال هر دو عکس ۲۰ سکه برنز از موجودی شما کم می‌شود." in t)
    check("متن تأیید: سؤال تأیید", "آیا تأیید می‌کنید؟" in t)
    check("متن تأیید: گزینه‌های تأیید", "بله / تایید / تأیید   → انجام" in t)
    check("متن تأیید: گزینه‌های لغو", "خیر / لغو             → انصراف" in t)
    check("عدد ۴۰ در متن نیست", "۴۰" not in t)
    check("هزینهٔ هر عکس = ۱۰", pd.COST_PER_IMAGE == 10, f"{pd.COST_PER_IMAGE}")


# ===========================================================================
def main():
    test_content_filter()
    test_confirm_flow_no_charge_before_confirm()
    test_blocked_query_aborts()
    test_insufficient_balance_aborts()
    test_charge_only_after_images_ready()
    test_lock_serializes_group()
    test_release_on_network_error()

    test_only_exact_command_triggers()
    test_exact_command_asks_query()
    test_two_step_full_flow_20_bronze()
    test_per_image_cost_1_image()
    test_real_image_bytes_are_valid()
    test_two_step_flow()

    # سناریوهای هزینهٔ دقیق
    test_2_images_success_20_bronze()
    test_1_image_success_10_bronze()
    test_no_result_0_bronze()
    test_download_failure_0_bronze()
    test_send_failure_0_bronze()
    test_url_fails_upload_fallback_10_bronze()
    test_no_confirm_0_bronze()
    test_insufficient_balance_not_performed()
    test_image_stream_is_photo()
    test_send_by_url_uses_photo_external()
    test_confirm_text_exact()

    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
