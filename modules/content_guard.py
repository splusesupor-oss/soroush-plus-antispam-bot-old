"""🛡️ نگهبان محتوا — بررسی متن آزاد پیش از ذخیره‌سازی ماندگار.

چرا یک ماژول جدا و چرا «لیست ساده» کافی نیست
--------------------------------------------
پروژه از قبل یک موتور واقعی تشخیص واژهٔ رکیک دارد:
``economy/name_filter.py``. آن موتور متن را پیش از مقایسه «فشرده»
می‌کند (حذف نویسهٔ نامرئی، نیم‌فاصله، کشیده، نقطه‌گذاری، تکرار حرف و
ترجمهٔ leetspeak) پس ترفندهایی مثل ``ک.ی.ر``، ``کییییر`` یا ``f4ck``
هم گرفته می‌شوند. این ماژول *همان* موتور را دوباره استفاده می‌کند و
موتور دوم و موازی نمی‌سازد.

تفاوت با ``name_filter.classify``
---------------------------------
``classify`` برای «نام و لقب» نوشته شده و یک قانون بسیار سخت‌گیرانه
دارد: واژهٔ کوتاه حتی اگر *داخل* یک واژهٔ دیگر باشد هم رد می‌شود. برای
نام درست است، ولی برای متن آزاد فاجعه است: ``class``، ``password`` یا
``https://t.me/classroom`` به‌خاطر ``ass`` رد می‌شدند.

پس اینجا همان مجموعه‌واژه‌ها و همان نرمال‌سازی به کار می‌رود، فقط با
قانون سالم‌تر برای متن آزاد:

* واژهٔ «بلند» (مثل ``کسکش``/``fuck``) هر جای متن باشد → رد
* واژهٔ «کوتاه» (مثل ``کس``/``ass``) فقط وقتی خودش یک واژهٔ مستقل باشد
* کل متنِ فشرده اگر خودش یک واژهٔ کوتاه باشد → رد (شکستن ``ک ی ر``)

به‌علاوه یک لایهٔ «محتوای جنسی» اضافه می‌شود که در ``name_filter``
نیست (آنجا فقط فحش و توهین فهرست شده) و دامنه‌های مسدود پروژه
(``data/blocked_sites.txt`` از طریق ``modules/site_policy.py``) هم
بررسی می‌شوند.
"""
from economy import name_filter
from modules import site_policy


BANNED = "banned"
RESTRICTED = "restricted"
BLOCKED_SITE = "blocked_site"

MESSAGE_BANNED = (
    "❌ این متن به دلیل داشتن محتوای غیرمجاز قابل ذخیره در کپی بورد نیست."
)
MESSAGE_RESTRICTED = MESSAGE_BANNED
MESSAGE_BLOCKED_SITE = (
    "❌ این متن به دلیل داشتن لینک غیرمجاز قابل ذخیره در کپی بورد نیست."
)


# ---------------------------------------------------------------------------
# لایهٔ «محتوای جنسی» — چیزی که فهرست نام/لقب پوشش نمی‌دهد.
#
# «بلند» = آن‌قدر مشخص است که داخل واژهٔ دیگر هم نامناسب است.
# «کوتاه» = فقط وقتی واژهٔ مستقل باشد (تا «sexton» یا «شهوت‌انگیز بودن
# یک غذا» قربانی نشود).
# ---------------------------------------------------------------------------
_SEXUAL_LONG = (
    "پورن", "پورنو", "سکسی", "سکسچت", "شهوانی", "همخوابگی",
    "porn", "pornhub", "hentai", "onlyfans", "camgirl", "nudes",
    "sexchat", "sextape", "escortservice",
)
_SEXUAL_SHORT = (
    "سکس", "شهوت", "برهنه", "لخت", "هرزگی",
    "sex", "sexy", "nude", "horny", "escort", "orgasm", "boobs",
)


def _prepare(words):
    """واژه‌ها را با همان فشرده‌سازی موتور اصلی آماده می‌کند."""
    prepared = []
    for word in words:
        try:
            squashed = name_filter._squash(word)
        except Exception:  # pragma: no cover - موتور همیشه موجود است
            squashed = ""
        # نویسه‌های تکراری در فشرده‌سازی حذف می‌شوند؛ واژه‌ای که بعد از
        # فشرده‌سازی خیلی کوتاه شود (مثل «xxx» → «x») به دام false positive
        # تبدیل می‌شود، پس کنار گذاشته می‌شود.
        if len(squashed) >= 3:
            prepared.append(squashed)
    return tuple(sorted(set(prepared), key=len, reverse=True))


_LONG_SET = tuple(getattr(name_filter, "_LONG_SET", ())) + _prepare(_SEXUAL_LONG)
_SHORT_SET = frozenset(getattr(name_filter, "_SHORT_SET", ())) | set(
    _prepare(_SEXUAL_SHORT))
_RESTRICTED_SET = tuple(getattr(name_filter, "_RESTRICTED_SET", ()))


def _strip_links(text):
    """لینک‌ها را از متن جدا می‌کند.

    بدون این کار مسیرِ یک لینک سالم (مثل ``/classroom``) می‌توانست
    واژهٔ کوتاه را در خود داشته باشد و متن بی‌گناه رد شود. خود لینک‌ها
    جداگانه با سیاست دامنهٔ پروژه بررسی می‌شوند.
    """
    value = str(text or "")
    found = site_policy.links(value)
    for link in found:
        value = value.replace(link, " ")
    return value, found


def classify_text(text):
    """نوع مشکل متن را برمی‌گرداند؛ ``None`` یعنی سالم."""
    raw = str(text or "")
    if not raw.strip():
        return None

    body, found_links = _strip_links(raw)

    for link in found_links:
        kind, _host = site_policy.classify(link)
        if kind == "blocked":
            return BLOCKED_SITE

    if not body.strip():
        return None

    variants = name_filter._squash_variants(body)
    if not variants:
        return None
    tokens = name_filter._tokens(body)

    for term in _RESTRICTED_SET:
        if term and any(term in variant for variant in variants):
            return RESTRICTED

    for term in _LONG_SET:
        if term and any(term in variant for variant in variants):
            return BANNED

    for token in tokens:
        if token in _SHORT_SET:
            return BANNED

    # متنی که کل فشرده‌اش یک واژهٔ کوتاه است: «ک ی ر» یا «k.i.r».
    if any(variant in _SHORT_SET for variant in variants):
        return BANNED

    return None


def message_for(kind):
    if kind == BLOCKED_SITE:
        return MESSAGE_BLOCKED_SITE
    if kind == RESTRICTED:
        return MESSAGE_RESTRICTED
    if kind == BANNED:
        return MESSAGE_BANNED
    return None


def check(text):
    """``(ok, message)`` — راحت‌ترین راه استفاده."""
    kind = classify_text(text)
    if kind is None:
        return True, None
    return False, message_for(kind)


def is_allowed(text):
    return classify_text(text) is None
