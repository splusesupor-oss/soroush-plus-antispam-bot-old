"""📥 قابلیت «دانلود عکس» — جدا و مستقل برای SPlusthon.

این ماژول با معماری فعلی ربات هماهنگ است:
  - از ``economy.get_balance`` / ``economy.spend`` برای سکه استفاده می‌کند.
  - با ``bot.client.send_file`` تصویر را مستقیم داخل چت می‌فرستد.
  - دستورِ «دانلود عکس» یک جریان تأییدی (confirm) دارد و فقط بعد از تأیید و
    آماده‌بودنِ تصاویر، هزینه کم می‌شود.

هزینه (ثابت و دقیق):
  - هر عکس = ۱۰ سکه برنز.
  - در هر درخواست حداکثر ۲ عکس ارسال می‌شود.
  - اگر ۲ عکس با موفقیت ارسال شود: ۲۰ برنز.
  - اگر فقط ۱ عکس با موفقیت ارسال شود: ۱۰ برنز.
  - اگر هیچ عکسی ارسال نشود: ۰ برنز.

رفتار:
  ۱) «دانلود عکس» → درخواستِ عبارت از کاربر + پیام تأیید هزینه.
  ۲) کاربر عبارت/تأیید یا لغو را می‌فرستد.
  ۳) قبل از تأیید هیچ سکه‌ای کم نمی‌شود.
  ۴) فقط بعد از تأیید: فیلترِ محتوای ممنوع → جستجو → دانلود تصاویر →
     ارسال در چت → سپس کسرِ سکه فقط بابت تصاویری که واقعاً با موفقیت
     دانلود و ارسال شده‌اند.
  ۵) قفلِ گروه + صفِ هر کاربر تا درخواست‌های هم‌زمان اجرا نشوند.

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

COST_PER_IMAGE = 10   # هزینهٔ دقیقِ هر عکس (برنز)
IMAGE_COUNT = 2       # حداکثر ۲ عکس در هر درخواست
SEND_RETRIES = 2      # تلاش مجدد برای ارسالِ هر عکس در صورت خطای گذرا
NETWORK_TIMEOUT = (10, 20)

# زمان انقضای جریانِ تأیید (ثانیه). بعد از آن، کاربر باید دوباره شروع کند.
CONFIRM_TIMEOUT = 120

COMMAND = "دانلود عکس"

CONFIRM_TEXT = (
    "📥 دانلود تصویر\n\n"
    "برای هر عکس ۱۰ سکه برنز نیاز است.\n"
    "برای دریافت حداکثر ۲ تصویر، در صورت ارسال هر دو عکس ۲۰ سکه برنز از موجودی شما کم می‌شود.\n\n"
    "آیا تأیید می‌کنید؟\n\n"
    "بله / تایید / تأیید   → انجام\n"
    "خیر / لغو             → انصراف"
)
INSUFFICIENT = ("❌ موجودی شما کمتر از ۱۰ سکه برنز است؛ این درخواست انجام نمی‌شود.")
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
    """عبارت را جستجو و آدرسِ مستقیمِ تصویر را برمی‌گرداند (همگام، داخل thread).

    ترتیب منابع (همه بدون کلید، روی Termux قابل اجرا):
      ۱) Bing Image — آدرسِ مستقیمِ فایلِ تصویر (برای فارسی و انگلیسی کار می‌کند).
      ۲) Openverse API — آدرسِ مستقیمِ تصویر.
    خروجی فقط «آدرسِ فایلِ تصویر» است، نه لینکِ صفحه/مقاله.
    """
    from urllib.parse import quote
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36"),
    }

    # ۱) Bing Image search
    try:
        url = "https://www.bing.com/images/search?q=" + quote(query)
        resp = requests.get(url, headers=headers, timeout=NETWORK_TIMEOUT)
        if resp.status_code == 200:
            html = resp.text
            urls = re.findall(r'murl&quot;:&quot;([^&]+)&quot;', html)
            urls += re.findall(r'"murl":"([^"]+)"', html)
            seen = []
            for u in urls:
                u = u.replace("\\/", "/").strip()
                if u and "http" in u and u not in seen:
                    seen.append(u)
                if len(seen) >= limit:
                    break
            if seen:
                return seen[:limit]
    except Exception:
        pass

    # ۲) Openverse API
    try:
        url = ("https://api.openverse.org/v1/images/?q="
               + quote(query) + "&page_size=15")
        resp = requests.get(url, headers=headers, timeout=NETWORK_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            urls = []
            for item in data.get("results", []):
                u = (item.get("url") or "").strip()
                if u and "http" in u and u not in urls:
                    urls.append(u)
                if len(urls) >= limit:
                    break
            if urls:
                return urls[:limit]
    except Exception:
        pass

    return []


def _fetch_image_bytes(url, timeout=NETWORK_TIMEOUT):
    """تصویر را دانلود و به bytes تبدیل می‌کند (همگام، داخل thread).

    از یک User-Agent شبیه مرورگر استفاده می‌شود؛ بعضی میزبان‌ها (مثل
    flickr) درخواستِ bot/ساده را رد می‌کنند. فقط محتوایی برمی‌گردد که
    شبیه فایلِ تصویر معتبر باشد.
    """
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36"),
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        return None
    content = resp.content
    if not content or len(content) < 100:
        return None
    # بررسیِ magic bytes تا مطمئن شویم فایلِ تصویر واقعی است، نه HTML/مقاله
    if content[:4] in (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1",
                       b"\xff\xd8\xff\xe8"):  # JPEG
        return content
    if content[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
        return content
    if content[:6] in (b"GIF87a", b"GIF89a"):  # GIF
        return content
    if content[:2] == b"BM":  # BMP
        return content
    if content[:4] == b"RIFF":  # WEBP
        return content
    return None


def _make_image_stream(data, index=0):
    """bytes تصویر را به یک استریمِ قابلِ ارسال با نام و پسوند معتبر تبدیل می‌کند.

    نکتهٔ مهم: وقتی فایل بدونِ ``name``/پسوند به ``send_file`` داده می‌شود،
    کتابخانه آن را به‌عنوان یک «سند» بدونِ پسوند (application/octet-stream)
    آپلود می‌کند و سرورِ سروش نمی‌تواند آن را به‌درستی به‌عنوان عکس بشناسد.
    با گذاشتنِ نامِ ``photo_<n>.jpg`` و موقعیتِ ابتدای جریان، تصویر به‌عنوان
    یک عکسِ واقعی (photo) با پسوند و mime درست آپلود و ارسال می‌شود.
    """
    stream = io.BytesIO(data)
    stream.name = f"photo_{int(index) + 1}.jpg"
    stream.seek(0)
    return stream


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
    if balance.get(economy.BRONZE, 0) < COST_PER_IMAGE:
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

        # ۲) دانلود تصاویر (خارج از حلقه)
        images = []
        for idx, url in enumerate(urls[:IMAGE_COUNT]):
            try:
                data = await asyncio.to_thread(_fetch_image_bytes, url)
            except Exception:
                data = None
            if data:
                images.append(_make_image_stream(data, idx))
            if len(images) >= IMAGE_COUNT:
                break
        if not images:
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        # ۳) ارسال در چت (نه لینک) — ابتدا ارسال می‌کنیم تا فقط در صورتِ
        # موفقیتِ واقعیِ ارسال، سکه کم شود. برای هر عکس تلاشِ مجددِ محدود
        # انجام می‌شود تا خطاهای گذرای سرور (مثل خطاهای آپلود فایل) منجر به
        # از دست رفتنِ بی‌دلیلِ عکس نشود.
        sent = 0
        for img in images:
            ok = False
            for attempt in range(SEND_RETRIES):
                # هر بار جریان را به ابتدا برمی‌گردانیم؛ چون ارسالِ ناموفق
                # جریان را تا همان‌جا مصرف کرده است و تلاشِ مجدد باید از
                # ابتدای فایلِ تصویر دوباره آپلود کند.
                img.seek(0)
                try:
                    await bot.client.send_file(chat_id, img)
                    ok = True
                    break
                except Exception:
                    if attempt + 1 < SEND_RETRIES:
                        await asyncio.sleep(0.6)
            if ok:
                sent += 1
            await asyncio.sleep(0.3)

        if sent == 0:
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        # ۴) کسرِ سکه — فقط بعد از موفقیتِ واقعیِ ارسال.
        #    هزینه = ۱۰ برنز به‌ازای هر عکسِ ارسال‌شده (۱ عکس = ۱۰، ۲ عکس = ۲۰).
        cost = COST_PER_IMAGE * sent
        try:
            economy.spend(
                chat_id, user_id, cost, economy.BRONZE,
                reference=f"photo_download:{chat_id}:{user_id}:{int(time.time())}",
                note=f"دانلود عکس ({sent} تصویر)",
            )
        except Exception:
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        close_session(chat_id, user_id)
        return "done", f"✅ {sent} تصویر ارسال شد. {cost} سکه برنز کسر شد."
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
