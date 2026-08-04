"""📥 قابلیت «دانلود عکس» — جدا و مستقل برای SPlusthon.

این ماژول با معماری فعلی ربات هماهنگ است:
  - از ``economy.get_balance`` / ``economy.spend`` برای سکه استفاده می‌کند.
  - با ``bot.client.send_file`` تصویر را مستقیم داخل چت می‌فرستد.
  - دستورِ «دانلود عکس» یک جریان تأییدی (confirm) دارد و فقط بعد از تأیید و
    آماده‌بودنِ تصاویر، ۲۰ سکه برنز کم می‌شود.

رفتار:
  ۱) «دانلود عکس» → درخواستِ عبارت از کاربر + پیام تأیید هزینه.
  ۲) کاربر عبارت/تأیید یا لغو را می‌فرستد.
  ۳) فقط بعد از تأیید: فیلترِ محتوای ممنوع → جستجو → دانلود ۲ تصویر →
     ارسال در چت → کسرِ ۲۰ برنز.
  ۴) قفلِ گروه + صفِ هر کاربر تا درخواست‌های هم‌زمان اجرا نشوند.

پایداری:
  - جستجو/دانلود داخل ``asyncio.to_thread`` تا Event Loop قفل نشود.
  - همهٔ عملیات شبکه timeout دارند و خطاها مدیریت می‌شوند.
  - هر خطا/لغو، وضعیتِ قفل و صف را آزاد می‌کند تا درخواست بعدی گیر نکند.
"""
import asyncio
import io
import re
import time

import requests

import economy

COST_BRONZE = 20
IMAGE_COUNT = 2
NETWORK_TIMEOUT = (10, 20)

# زمان انقضای جریانِ تأیید (ثانیه). بعد از آن، کاربر باید دوباره شروع کند.
CONFIRM_TIMEOUT = 120

COMMAND = "دانلود عکس"

CONFIRM_TEXT = (
    "📥 دانلود تصویر\n\n"
    "برای دریافت ۲ تصویر از این جستجو، ۲۰ سکه برنز از موجودی شما کم می‌شود.\n"
    "آیا تأیید می‌کنید؟\n\n"
    "بله / تایید / تأیید   → انجام\n"
    "خیر / لغو             → انصراف"
)
INSUFFICIENT = "❌ موجودی شما کمتر از ۲۰ سکه برنز است؛ این درخواست انجام نمی‌شود."
BLOCKED_CONTENT = "🚫 این درخواست ممنوع است و قابل انجام نیست."
CANCELLED = "❌ درخواست لغو شد؛ هیچ سکه‌ای کم نشد."
BUSY_GROUP = "⏳ یک دانلود عکس در همین گروه در حال پردازش است؛ لطفاً صبر کنید."
BUSY_USER = "⏳ شما درخواستِ دانلود عکسِ در حال پردازش دارید؛ لطفاً صبر کنید."
ASK_QUERY = "🖼️ چه تصویری می‌خواهید؟ عبارت موردنظر خود را بنویسید."
ERROR_MSG = "❌ مشکلی در جستجو/دانلود پیش آمد؛ دوباره تلاش کنید. هیچ سکه‌ای کم نشد."
NO_RESULTS = "🔍 نتیجه‌ای برای این عبارت پیدا نشد؛ هیچ سکه‌ای کم نشد."

# ---------------------------------------------------------------------------
#  کلمات/عبارت‌های ممنوع — فارسی و انگلیسی
# ---------------------------------------------------------------------------
_BANNED_WORDS_FA = {
    "سکس", "سکسی", "پورن", "پورنو", "برهنه", "برهنه‌ها", "لخت", "لختی",
    "عریان", "عریانی", "جنسى", "جنسی", "رابطه جنسی", "مست", "مست‌کننده",
    "اسپرم", "کیر", "کص", "کون", "جنده", "فحش", "فحاشی", "دیوث", "هرزه",
    "هرزگی", "سکسی", "بیکینی", "بی‌کینی", "پستان", "سینه‌برهنه",
    "نود", "نودی", "عکس مست", "امراض جنسی", "مقاربت", "آمیزش",
    "اروتیک", "اروتیسم",
}
_BANNED_WORDS_EN = {
    "sex", "porn", "porno", "nude", "naked", "nsfw", "erotic", "xxx",
    "fuck", "pussy", "dick", "cock", "hentai", "boobs", "anal", "blowjob",
    "bikini", "lingerie", "strip", "stripper", "escort", "orgy", "masturb",
    "thong", "nude photography", "18+", "adult content", "pornstar",
}
# برای تشخیصِ صریحِ «عبارت جنسی» حتی اگر دقیقاً کلمهٔ ممنوع نباشد.
_BANNED_PATTERNS = [
    r"برهنه", r"لخت", r"عکس\s*مست", r"سکس", r"پورن", r"جنسی",
    r"nude", r"naked", r"porn", r"sex", r"nsfw", r"erotic", r"xxx",
]

# ---------------------------------------------------------------------------
#  وضعیت — به تفکیک (chat, user)
# ---------------------------------------------------------------------------
_SESSIONS = {}       # (chat_id, user_id) -> {"query": str, "ts": float}
_GROUP_LOCKS = {}    # chat_id -> asyncio.Lock
_BUSY_GROUPS = set()  # chat_id هایی که در حال پردازش‌اند
_BUSY_USERS = set()   # (chat_id, user_id) هایی که در حال پردازش‌اند


def reset_all():
    """پاک‌سازی کامل — برای تست/ری‌استارت."""
    _SESSIONS.clear()
    _GROUP_LOCKS.clear()
    _BUSY_GROUPS.clear()
    _BUSY_USERS.clear()


def _group_lock(chat_id):
    lock = _GROUP_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _GROUP_LOCKS[chat_id] = lock
    return lock


def is_busy(chat_id, user_id):
    return chat_id in _BUSY_GROUPS or (chat_id, user_id) in _BUSY_USERS


# ---------------------------------------------------------------------------
#  فیلتر محتوای ممنوع
# ---------------------------------------------------------------------------
def _norm(value):
    text = (value or "").strip().lower()
    # یکسان‌سازی حروف فارسی
    for a, b in (("ي", "ی"), ("ك", "ک"), ("\u200c", " "), ("\u200f", "")):
        text = text.replace(a, b)
    return " ".join(text.split())


def is_blocked(query):
    """اگر درخواست، صریحاً برای محتوای جنسی/مستهجن باشد → True."""
    norm = _norm(query)
    tokens = set(norm.split())
    for w in _BANNED_WORDS_FA:
        if _norm(w) in norm:
            return True
    for w in _BANNED_WORDS_EN:
        if w in norm:
            return True
    # عبارت‌های ترکیبی
    for pat in _BANNED_PATTERNS:
        if re.search(pat, norm):
            return True
    # تشخیصِ «به شکل واضح برای پیدا کردن محتوای جنسی» حتی بدون کلمهٔ ممنوع
    if any(t in tokens for t in ("عکس", "تصویر", "تصاویر", "photo", "pic", "image")):
        if any(t in tokens for t in ("مست", "برهنه", "لخت", "جنسی", "سکس",
                                     "nude", "naked", "sex", "nsfw", "porn")):
            return True
    return False


# ---------------------------------------------------------------------------
#  جستجو و دانلود تصویر (خارج از Event Loop، با timeout)
# ---------------------------------------------------------------------------
def _search_image_urls(query, limit=IMAGE_COUNT):
    """عبارت را جستجو و آدرس تصویر را برمی‌گرداند (همگام، داخل thread)."""
    from urllib.parse import quote
    url = "https://html.duckduckgo.com/html/?q=" + quote(query + " تصویر")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SoroushPlusSearch/1.0)"}
    resp = requests.get(url, headers=headers, timeout=NETWORK_TIMEOUT)
    if resp.status_code != 200:
        return []
    html = resp.text
    # استخراج آدرس‌های تصویر از نتایج DuckDuckGo
    urls = []
    # الگوی استاندارد تصاویر DDG: "img" با srcdata
    for m in re.findall(r'data-src="([^"]+)"', html):
        u = m.strip()
        if u and not u.endswith((".gif",)) and "//" in u:
            if u not in urls:
                urls.append(u)
        if len(urls) >= limit:
            break
    if len(urls) < limit:
        # fallback: هر لینک خارجی
        for m in re.findall(r'href="([^"]+)"', html):
            u = m.strip()
            if "duckduckgo" in u or "uddg=" in u:
                continue
            if "http" in u and "ir.lih" not in u and u not in urls:
                urls.append(u)
            if len(urls) >= limit:
                break
    return urls[:limit]


def _fetch_image_bytes(url, timeout=NETWORK_TIMEOUT):
    """تصویر را دانلود و به bytes تبدیل می‌کند (همگام، داخل thread)."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SoroushPlusSearch/1.0)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        return None
    return resp.content


# ---------------------------------------------------------------------------
#  API عمومی برای هندلر
# ---------------------------------------------------------------------------
def start_session(chat_id, user_id):
    """شروع جریانِ «دانلود عکس»؛ درخواستِ عبارت."""
    key = (chat_id, user_id)
    _SESSIONS[key] = {"query": None, "ts": time.monotonic()}


def session(chat_id, user_id):
    """دادهٔ جریانِ تأییدِ این کاربر، یا None."""
    key = (chat_id, user_id)
    s = _SESSIONS.get(key)
    if s is None:
        return None
    if time.monotonic() - s["ts"] > CONFIRM_TIMEOUT:
        _SESSIONS.pop(key, None)
        return None
    return s


def close_session(chat_id, user_id):
    _SESSIONS.pop((chat_id, user_id), None)


def handle_query(chat_id, user_id, query):
    """بعد از دریافت عبارت، عبارت را ذخیره و پیام تأیید برمی‌گرداند.

    خروجی: ("ask_confirm", confirm_text) یا ("blocked", msg) یا
            ("insufficient", msg) یا ("start_processing", None).
    """
    key = (chat_id, user_id)
    s = _SESSIONS.get(key)
    if s is None:
        return "no_session", None

    if is_blocked(query):
        close_session(chat_id, user_id)
        return "blocked", BLOCKED_CONTENT

    balance = economy.get_balance(chat_id, user_id)
    if balance.get(economy.BRONZE, 0) < COST_BRONZE:
        close_session(chat_id, user_id)
        return "insufficient", INSUFFICIENT

    s["query"] = query
    s["ts"] = time.monotonic()
    return "ask_confirm", CONFIRM_TEXT


def handle_confirm(chat_id, user_id, text):
    """بررسی پاسخِ تأیید/لغو.

    خروجی: ("cancel", msg) یا ("start", None) یا ("no_session", None) یا
            ("invalid", msg).
    """
    key = (chat_id, user_id)
    s = _SESSIONS.get(key)
    if s is None or s.get("query") is None:
        return "no_session", None
    norm = _norm(text)
    if norm in {"لغو", "خیر", "نه", "انصراف", "بی‌خیال", "cancel", "no"}:
        close_session(chat_id, user_id)
        return "cancel", CANCELLED
    if norm in {"بله", "تایید", "تأیید", "آره", "بفرست", "ارسال", "ok", "yes", "بله بفرست"}:
        return "start", None
    return "invalid", CONFIRM_TEXT


async def process(chat_id, user_id, bot):
    """اجرای کاملِ جستجو/دانلود/ارسال/کسرِ سکه، با قفلِ گروه و صفِ کاربر.

    فقط وقتی فراخوانی می‌شود که تأیید شده و هنوز هیچ‌چیز کم نشده است.
    در پایان (موفق یا خطا) قفل/صف آزاد می‌شوند.
    """
    key = (chat_id, user_id)
    query = None
    s = _SESSIONS.get(key)
    if s is not None:
        query = s.get("query")
    if not query:
        close_session(chat_id, user_id)
        _release_busy(chat_id, user_id)
        return "no_session", None

    lock = _group_lock(chat_id)
    if not lock.locked():
        # فقط یک دانلود هم‌زمان در هر گروه
        await lock.acquire()
    _BUSY_GROUPS.add(chat_id)
    _BUSY_USERS.add(key)
    try:
        # ۱) جستجو (خارج از حلقه)
        try:
            urls = await asyncio.to_thread(_search_image_urls, query)
        except Exception:
            urls = []
        if not urls:
            close_session(chat_id, user_id)
            return "no_results", NO_RESULTS

        # ۲) دانلود ۲ تصویر (خارج از حلقه)
        images = []
        for url in urls[:IMAGE_COUNT]:
            try:
                data = await asyncio.to_thread(_fetch_image_bytes, url)
            except Exception:
                data = None
            if data:
                images.append(io.BytesIO(data))
            if len(images) >= IMAGE_COUNT:
                break
        if not images:
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        # ۳) کسرِ سکه — فقط وقتی تصاویر واقعاً آماده‌اند
        try:
            economy.spend(
                chat_id, user_id, COST_BRONZE, economy.BRONZE,
                reference=f"photo_download:{chat_id}:{user_id}:{int(time.time())}",
                note="دانلود عکس (۲ تصویر)",
            )
        except Exception:
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        # ۴) ارسال در چت (نه لینک)
        sent = 0
        for img in images:
            try:
                await bot.client.send_file(chat_id, img)
                sent += 1
            except Exception:
                break
            await asyncio.sleep(0.3)

        close_session(chat_id, user_id)
        if sent == 0:
            return "error", ERROR_MSG
        return "done", f"✅ {sent} تصویر ارسال شد. {COST_BRONZE} سکه برنز کسر شد."
    finally:
        _release_busy(chat_id, user_id)


def _release_busy(chat_id, user_id):
    """آزادسازی قفل/صف — همیشه در finally صدا زده می‌شود."""
    _BUSY_GROUPS.discard(chat_id)
    _BUSY_USERS.discard((chat_id, user_id))
    lock = _GROUP_LOCKS.get(chat_id)
    if lock is not None and lock.locked():
        try:
            lock.release()
        except Exception:
            pass
