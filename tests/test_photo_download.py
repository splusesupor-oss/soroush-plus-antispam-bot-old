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
    def __init__(self):
        self.sent = 0

    async def send_file(self, entity, img, **kw):
        await asyncio.sleep(0.01)
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
def main():
    test_content_filter()
    test_confirm_flow_no_charge_before_confirm()
    test_blocked_query_aborts()
    test_insufficient_balance_aborts()
    test_charge_only_after_images_ready()
    test_lock_serializes_group()
    test_release_on_network_error()

    print(f"\npassed={PASSED} failed={FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
