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
import logging
import re
import time
import traceback
from urllib.parse import quote, urlparse

import requests

import economy

COST_PER_IMAGE = 10   # هزینهٔ دقیقِ هر عکس (برنز)
IMAGE_COUNT = 2       # حداکثر ۲ عکس در هر درخواست
SEARCH_CANDIDATES = 8  # تعدادِ نامزدِ جستجو برای اینکه حداقل ۲ عکسِ معتبر پیدا شود
SEND_RETRIES = 2      # تلاش مجدد برای ارسالِ هر عکس در صورت خطای گذرا
NETWORK_TIMEOUT = (10, 20)
# حداکثرِ زمانِ کلِ یک لینک (دانلود + ارسال). اگر لینکی بیشتر از این طول کشید،
# رد می‌شود و سراغِ لینکِ بعدی می‌رویم تا کل عملیات مدت‌ها درگیر یک لینک نشود.
LINK_TIMEOUT = 10
# سقفِ زمانیِ کلِ عملیاتِ یک درخواست (جستجو + تلاش روی چند لینک + ارسال).
# بعد از این زمان، دیگر لینکِ جدیدی تست نمی‌شود تا عملیات چند دقیقه معطل نماند.
PROCESS_TIMEOUT = 45

# پسوندِ فایلِ تصویر — برای تشخیصِ آدرسِ مستقیمِ فایل
_IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|avif|bmp)([?#;].*)?$", re.I)

# میزبان‌هایِ پایدارِ CDN که دانلودِ مستقیمِ تصویر می‌دهند (نه لینکِ صفحه).
# این منابع معمولاً فایلِ تصویر را مستقیم و بدونِ صفحه/HTML برمی‌گردانند.
_RELIABLE_HOSTS = (
    "pinimg.com",             # Pinterest — i.pinimg.com (مستقیم و پایدار)
    "unsplash.com",           # images.unsplash.com
    "pexels.com",             # images.pexels.com
    "wikimedia.org",          # upload.wikimedia.org (ویکی‌انبار)
    "flickr.com",             # live.staticflickr.com / farm*.staticflickr.com
    "pixabay.com",            # cdn.pixabay.com
    "istockphoto.com",        # media.istockphoto.com
    "gettyimages.com",        # media.gettyimages.com
    "googleusercontent.com",  # lh3.googleusercontent.com
    "gstatic.com",            # www.gstatic.com
    "ytimg.com",              # i.ytimg.com
    "wixstatic.com",          # static.wixstatic.com
    "amazonaws.com",          # *.s3.amazonaws.com
    "cloudfront.net",         # *.cloudfront.net
    "githubusercontent.com",
    "imgur.com",              # i.imgur.com
    "tenor.com",              # media.tenor.com (gif)
    "giphy.com",              # media.giphy.com
    "twimg.com",              # pbs.twimg.com
    "wp.com",
    "wordpress.com",
)

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
# دامنه‌های اسپم/تبلیغاتی/کازینو/نامرتبط که نباید عکس از آن‌ها گرفته شود.
_SPAM_KEYWORDS = (
    "casino", "bet", "betting", "slot", "poker", "gambling", "bonus",
    "offer", "deal", "discount", "coupon", "promo", "advert", "click",
    "track", "redirect", "shortener", "bit.ly", "t.ly", "cutt.ly",
)
_SPAM_TLDS = (
    ".click", ".loan", ".cash", ".buzz", ".xyz", ".top", ".icu", ".gq",
    ".ml", ".ga", ".cf", ".tk", ".men", ".win", ".bid", ".trade", ".review",
    ".cam", ".rest", ".mom", ".lol",
)


def _is_spam_url(url):
    """آیا این URL یک دامنهٔ اسپم/تبلیغاتی/کازینو یا نامرتبط است؟"""
    if not url:
        return True
    host = (urlparse(url).netloc or "").lower()
    if not host:
        return True
    # دامنهٔ ناقص/محلی
    if host.startswith(("localhost", "127.", "0.")):
        return True
    # TLD اسپم
    for tld in _SPAM_TLDS:
        if host.endswith(tld):
            return True
    # کلمهٔ اسپم در دامنه یا مسیر
    full = (host + " " + urlparse(url).path).lower()
    for kw in _SPAM_KEYWORDS:
        if kw in full:
            return True
    return False


# نقشهٔ سادهٔ نویسهٔ فارسی → لاتین برای جستجویِ بهتر (مثل «رونالدو» → ronaldo).
_FA_TO_LATIN = {
    "ا": "a", "آ": "a", "ب": "b", "پ": "p", "ت": "t", "ث": "s", "ج": "j",
    "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ذ": "z", "ر": "r", "ز": "z",
    "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t", "ظ": "z",
    "ع": "", "غ": "gh", "ف": "f", "ق": "q", "ک": "k", "گ": "g", "ل": "l",
    "م": "m", "ن": "n", "و": "v", "ه": "h", "ی": "y", "ئ": "e", "ء": "",
    "،": ",", "؟": "?", " ": " ",
}


def _transliterate_fa(text):
    """تبدیلِ سادهٔ متنِ فارسی به نویسهٔ لاتین (برای جستجو)."""
    out = []
    for ch in text:
        out.append(_FA_TO_LATIN.get(ch, ch))
    return "".join(out).strip()


def _is_direct_image_url(url):
    """آیا این URL یک آدرسِ مستقیمِ قابلِ دانلودِ تصویر است؟

    - از یک میزبانِ CDNِ شناخته‌شده باشد (که فایلِ تصویر را مستقیم می‌دهد)،
      یا
    - پسوندِ فایلِ تصویر داشته باشد (.jpg/.png/...).
    لینکِ صفحه/مقاله (که فقط داخل مرورگر باز می‌شود و دانلودِ مستقیم نمی‌دهد)
    و دامنه‌هایِ اسپم/تبلیغاتی/کازینو/فروشگاهی رد می‌شوند تا ربات سراغِ
    لینک‌هایِ ناکارآمد یا نامرتبط نرود.
    """
    if not url:
        return False
    if _is_spam_url(url):
        return False
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    if any(host == h or host.endswith("." + h) for h in _RELIABLE_HOSTS):
        return True
    return bool(_IMAGE_EXT_RE.search(url))


def _search_openverse(query, limit):
    """جستجو در Openverse (واقعی و مرتبط‌تر، مخصوصاً برای فارسی)."""
    from urllib.parse import quote
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36"),
    }
    url = ("https://api.openverse.org/v1/images/?q="
           + quote(query) + "&page_size=20")
    resp = requests.get(url, headers=headers, timeout=NETWORK_TIMEOUT)
    if resp.status_code != 200:
        return []
    data = resp.json()
    seen = []
    for item in data.get("results", []):
        u = (item.get("url") or "").strip()
        if u and "http" in u and u not in seen:
            seen.append(u)
    return [u for u in seen if _is_direct_image_url(u)][:limit]


def _search_bing(query, limit):
    """جستجو در Bing Image (مکمل)."""
    from urllib.parse import quote
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36"),
    }
    url = "https://www.bing.com/images/search?q=" + quote(query)
    resp = requests.get(url, headers=headers, timeout=NETWORK_TIMEOUT)
    if resp.status_code != 200:
        return []
    html = resp.text
    urls = re.findall(r'murl&quot;:&quot;([^&]+)&quot;', html)
    urls += re.findall(r'"murl":"([^"]+)"', html)
    seen = []
    for u in urls:
        u = u.replace("\\/", "/").strip()
        if u and "http" in u and u not in seen:
            seen.append(u)
    return [u for u in seen if _is_direct_image_url(u)][:limit]


def _search_image_urls(query, limit=IMAGE_COUNT):
    """عبارت را جستجو و آدرسِ مستقیمِ تصویرِ مرتبط را برمی‌گرداند (همگام).

    استراتژیِ بهتر برای فارسی:
      ۱) Openverse — نتایجِ مرتبط و پایدار (پاسخِ خوب برای فارسی).
      ۲) اگر عبارت فارسی بود، با نویسه‌گردانیِ لاتین (مثل «رونالدو» → ronaldo)
         هم جستجو می‌شود تا نتایجِ انگلیسیِ مرتبط هم بیاید.
      ۳) Bing به‌عنوان مکمل.
    خروجی فقط «آدرسِ فایلِ تصویر» است (لینکِ صفحه/مقاله نه) و لینک‌هایِ
    اسپم/فروشگاهی/نامرتبط حذف شده‌اند.
    """
    combined = []

    # ۱) Openverse با خودِ عبارت
    try:
        combined += _search_openverse(query, limit)
    except Exception:
        pass

    # ۲) اگر عبارت فارسی بود، با نویسهٔ لاتینِ آن هم جستجو کن
    latin = _transliterate_fa(query)
    if latin and latin.lower() != query.lower():
        try:
            combined += _search_openverse(latin, limit)
        except Exception:
            pass

    # ۳) Bing (هم با عبارت و هم لاتین)
    for q in (query, latin):
        if not q:
            continue
        try:
            combined += _search_bing(q, limit)
        except Exception:
            pass

    # حذفِ تکراری و قطع روی limit
    seen, out = set(), []
    for u in combined:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out[:limit]


def _is_valid_image_bytes(content):
    """بررسیِ magic bytes؛ صرفاً بر اساسِ محتوا، نه content-type.

    اگر سایت content-type اشتباه بدهد ولی bytes واقعاً تصویرِ معتبر باشد،
    اینجا رد نمی‌شود.
    """
    if not content:
        return False
    # JPEG — خانوادهٔ \xff\xd8\xff (اکثر عکس‌ها)
    if content[:3] == b"\xff\xd8\xff":
        return True
    # PNG
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    # GIF
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return True
    # BMP
    if content[:2] == b"BM":
        return True
    # WebP — RIFF....WEBP
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return True
    # AVIF — 'ftypavif'/'ftypavis' در ابتدای فایل
    if b"ftypavif" in content[:32] or b"ftypavis" in content[:32]:
        return True
    return False


def _fetch_image_bytes(url, timeout=NETWORK_TIMEOUT, log_func=None):
    """تصویر را دانلود و به bytes تبدیل می‌کند (همگام، داخل thread).

    هدرِ مرورگر + Accept برای تصویر فرستاده می‌شود تا سایت‌ها به‌جای صفحهٔ
    HTML خودِ عکس را بدهند. فقط محتوایی برمی‌گردد که magic bytes معتبرِ
    تصویر داشته باشد؛ دربارهٔ content-type تصمیم نمی‌گیرد.
    """
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36"),
        "Accept": ("image/avif,image/webp,image/apng,image/*,*/*;q=0.8"),
        "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
        "Referer": "https://www.bing.com/",
    }
    if log_func:
        log_func(f"DOWNLOAD REQUEST url={url}")
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        if log_func:
            log_func(f"DOWNLOAD ERROR url={url} reason={type(e).__name__}: {e}\n"
                     f"{traceback.format_exc()}")
        return None
    content = resp.content
    magic = content[:20]
    if log_func:
        log_func(
            f"DOWNLOAD url={url} status={resp.status_code} "
            f"type={resp.headers.get('Content-Type')} bytes={len(content)} "
            f"magic={magic.hex()}")
    if resp.status_code != 200:
        if log_func:
            log_func(f"DOWNLOAD reject reason=status_{resp.status_code}")
        return None
    if not content or len(content) < 100:
        if log_func:
            log_func("DOWNLOAD reject reason=size_too_small")
        return None
    if not _is_valid_image_bytes(content):
        if log_func:
            log_func("DOWNLOAD reject reason=bad_magic")
        return None
    if log_func:
        log_func("DOWNLOAD accept")
    return content


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


def _log(bot, message):
    """لاگِ امن روی logger ربات (و logger استانداردِ پایتون).

    اگر logger ربات در دسترس نبود، به loggerِ پایتون می‌رود تا چیزی
    بی‌صدا از دست نرود.
    """
    logging.getLogger("photo_download").info(message)
    try:
        bot.logger.log_info(message)
    except Exception:
        pass


def _log_exception(bot, context):
    """لاگِ کاملِ استثناء با traceback — تا معلوم شود مشکل از کجاست.

    از ``logger.exception`` استفاده می‌کند که خودش tracebackِ جاری را
    می‌گیرد. اگر logger ربات در دسترس نبود، به loggerِ پایتون و
    ``bot.logger.log_error`` برمی‌گردد.
    """
    tb = traceback.format_exc()
    msg = f"{context}\n{tb}"
    try:
        underlying = getattr(bot.logger, "logger", None)
        if underlying is not None and hasattr(underlying, "exception"):
            underlying.exception(context)
        else:
            bot.logger.log_error(msg)
    except Exception:
        logging.getLogger("photo_download").exception(context)
    # همیشه یک کپی در فایلِ لاگ ربات هم بنویس (اگر روش بالا جواب نداد)
    try:
        bot.logger.log_error(msg)
    except Exception:
        pass


async def _send_by_url(bot, chat_id, url):
    """ارسالِ عکس با URL (InputMediaPhotoExternal).

    در این روش سرورِ سروش خودش تصویر را از ``url`` می‌گیرد و آن را به‌صورت
    یک عکسِ واقعی داخل چت می‌فرستد. **هیچ آپلودی رخ نمی‌دهد** و درخواستِ
    ``upload.saveFilePart`` ساخته نمی‌شود؛ بنابراین خطای
    ``FILE_REQUEST_RECEIVED_ON_CONNECTION_SERVER`` پیش نمی‌آید.
    """
    from splusthon.tl import types, functions
    entity = await bot.client.get_input_entity(chat_id)
    media = types.InputMediaPhotoExternal(url=url)
    request = functions.messages.SendMediaRequest(entity, media, message="")
    await bot.client(request)
    return True


async def _download_valid(bot, url):
    """دانلود و اعتبارسنجیِ یک عکس؛ اگر واقعاً تصویرِ معتبر باشد bytes برمی‌گرداند.

    در غیرِ این صورت None برمی‌گرداند (عکسِ خراب/نامعتبر رد می‌شود تا لینکِ
    شکسته ارسال نشود).
    """
    _log(bot, f"PHOTO DOWNLOAD START url={url}")
    try:
        data = await asyncio.wait_for(
            asyncio.to_thread(
                _fetch_image_bytes, url,
                log_func=lambda m: _log(bot, m)),
            timeout=LINK_TIMEOUT)
    except asyncio.TimeoutError:
        _log(bot, f"PHOTO DOWNLOAD TIMEOUT url={url} timeout={LINK_TIMEOUT}s")
        return None
    except Exception:
        _log_exception(bot, f"PHOTO DOWNLOAD ERROR url={url}")
        return None
    if not data:
        _log(bot, f"PHOTO DOWNLOAD FAILED url={url} reason=download_invalid")
        return None
    _log(bot, f"PHOTO DOWNLOAD OK url={url} bytes={len(data)}")
    return data


async def _upload_album(bot, chat_id, items, force_reconnect=False):
    """ارسالِ همهٔ عکس‌هایِ معتبر با هم به‌صورتِ یک آلبوم (نه جدا جدا).

    items = [(url, bytes), ...]. اگر media sender نبود/قطع بود و
    force_reconnect=True، قبل از آپلود دوباره ساخته می‌شود.
    """
    if not items:
        return False
    streams = []
    for idx, (_url, data) in enumerate(items):
        streams.append(_make_image_stream(data, idx))
    if force_reconnect and hasattr(bot.client, "_call"):
        try:
            from modules.splusthon_upload_fix import _get_media_sender
            await _get_media_sender(bot.client, force_reconnect=True)
        except Exception:
            pass
    try:
        await asyncio.wait_for(
            bot.client.send_file(chat_id, streams), timeout=LINK_TIMEOUT * len(items))
        _log(bot, f"PHOTO SEND OK method=album count={len(items)}")
        return True
    except asyncio.TimeoutError:
        _log(bot, f"PHOTO SEND TIMEOUT method=album count={len(items)}")
    except Exception:
        _log_exception(bot, f"PHOTO SEND ERROR method=album count={len(items)}")
    return False


async def _send_links_together(bot, chat_id, items):
    """fallback: همهٔ لینک‌هایِ معتبر را در یک پیامِ متن می‌فرستد (نه جدا جدا).

    فقط لینکِ عکس‌هایی که واقعاً معتبر دانلود شده‌اند فرستاده می‌شود؛ هرگز
    لینکِ شکسته/نامعتبر.
    """
    urls = [u for u, _data in items]
    text = "🖼️ تصویر (لینک‌هایِ مستقیم):\n" + "\n".join(urls)
    await bot.client.send_message(chat_id, text)
    return True


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
        _log(bot, f"PHOTO SEARCH START chat_id={chat_id} user_id={user_id} query={query!r}")
        try:
            urls = await asyncio.to_thread(_search_image_urls, query, SEARCH_CANDIDATES)
        except Exception:
            _log_exception(bot, f"PHOTO SEARCH EXCEPTION query={query!r}")
            urls = []
        _log(bot, f"PHOTO URL FOUND count={len(urls)} query={query!r}")
        if not urls:
            close_session(chat_id, user_id)
            return "no_results", NO_RESULTS

        # ۲) جستجو نتیجه نداد
        if not urls:
            close_session(chat_id, user_id)
            return "no_results", NO_RESULTS

        # ۳) جمع‌آوری عکس‌هایِ معتبر (حداکثر IMAGE_COUNT) از بین نامزدها.
        #    اگر یک URL خراب/نامعتبر باشد، کل درخواست شکست نمی‌خورد؛ رد می‌شود
        #    و سراغِ لینکِ بعدی می‌رویم. فقط عکسِ واقعاً معتبر (bytes درست)
        #    نگه داشته می‌شود تا لینکِ شکسته ارسال نشود.
        deadline = time.monotonic() + PROCESS_TIMEOUT
        items = []  # [(url, bytes), ...]
        for url in urls:
            if len(items) >= IMAGE_COUNT:
                break
            if time.monotonic() >= deadline:
                _log(bot, f"PHOTO PROCESS TIMEOUT chat_id={chat_id} "
                          f"user_id={user_id} exceeded {PROCESS_TIMEOUT}s")
                break
            data = await _download_valid(bot, url)
            if data:
                items.append((url, data))
            await asyncio.sleep(0.2)

        if not items:
            _log(bot, f"PHOTO DOWNLOAD FAILED chat_id={chat_id} user_id={user_id} "
                      f"query={query!r} no valid image (all links failed)")
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        # ۴) ارسالِ همهٔ عکس‌هایِ معتبر با هم (آلبوم) — نه جدا جدا.
        #    ترتیب: آپلودِ آلبوم → تلاشِ مجدد با reconnect → لینکِ مستقیمِ
        #    فقطِ عکس‌هایِ معتبر (در یک پیام). اگر هیچ‌کدام نشد → خطا.
        delivered = 0
        if await _upload_album(bot, chat_id, items):
            delivered = len(items)
        elif await _upload_album(bot, chat_id, items, force_reconnect=True):
            delivered = len(items)
        else:
            # fallback: لینکِ عکس‌هایِ معتبر در یک پیام (هرگز لینکِ شکسته)
            _log(bot, f"PHOTO FALLBACK to direct links count={len(items)}")
            try:
                await asyncio.wait_for(
                    _send_links_together(bot, chat_id, items), timeout=LINK_TIMEOUT)
                _log(bot, "PHOTO SEND OK method=direct_links")
                delivered = len(items)
            except asyncio.TimeoutError:
                _log(bot, f"PHOTO SEND TIMEOUT method=direct_links "
                          f"timeout={LINK_TIMEOUT}s")
            except Exception:
                _log_exception(bot, "PHOTO SEND ERROR method=direct_links")

        if delivered == 0:
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        # ۵) کسرِ سکه — فقط بعد از موفقیتِ واقعیِ ارسال.
        #    هزینه = ۱۰ برنز به‌ازای هر عکسِ ارسال‌شده (۱ عکس = ۱۰، ۲ عکس = ۲۰).
        cost = COST_PER_IMAGE * delivered
        try:
            economy.spend(
                chat_id, user_id, cost, economy.BRONZE,
                reference=f"photo_download:{chat_id}:{user_id}:{int(time.time())}",
                note=f"دانلود عکس ({delivered} تصویر)",
            )
        except Exception:
            _log_exception(bot, f"PHOTO DOWNLOAD FAILED (spend) chat_id={chat_id} "
                                f"user_id={user_id} cost={cost}")
            close_session(chat_id, user_id)
            return "error", ERROR_MSG

        close_session(chat_id, user_id)
        return "done", f"✅ {delivered} تصویر ارسال شد. {cost} سکه برنز کسر شد."
    except Exception:
        # لایهٔ نهایی: هر خطایِ پیش‌بینی‌نشده را با traceback ثبت کن و به‌جایِ
        # پیامِ عمومیِ خام، علت را در لاگ نگه دار (بدون این لاگ نمی‌شود فهمید
        # مشکل از جستجو/لینک/دانلود/ارسال است).
        _log_exception(bot, f"PHOTO DOWNLOAD FAILED (unexpected) "
                            f"chat_id={chat_id} user_id={user_id} query={query!r}")
        close_session(chat_id, user_id)
        return "error", ERROR_MSG
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
