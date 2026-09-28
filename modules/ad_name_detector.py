"""تشخیص مستقل نام‌های تبلیغاتی؛ جدا از فیلتر متن گروه.

نسخهٔ تقویت‌شده در برابر دور زدن فیلتر:

- فاصله/نیم‌فاصله/خط تیره/کاراکترهای جداکننده بین حروف (س ک س، س‌ک‌س، س.ک.س)
- کشیده «ـ» و اعراب (بیـــو، سـکـس)
- تکرار حروف (سکسس، سسکس، دختترر)
- حروف مشابه Unicode و NFKC (ي/ك → ی/ک، 𝕤𝕖𝕩 → sex)
- جانشینی‌های رایج برای کلمات حساس «سکس» و «بیوگرافی»
  (ثکث، س۶س، سkس، سکث، بیوکرافی، biography، sex)
- ایموجی‌های تبلیغاتی، حتی بین فاصله/تکرار

هر نام روی چند نسخهٔ نرمال‌شده بررسی می‌شود: متن عادی، بدون حروف
تکراری، بدون فاصله، و «فقط حروف/ارقام». بین حروفِ یک الگو فقط
فاصله/جداکننده مجاز است، نه حرف واقعی دیگر؛ برای همین کلمات با
شباهت جزئی (مثل «پرستو» یا «خانم») false positive نمی‌گیرند.
"""
import re
import unicodedata

from modules.user_display import format_user

# ---------------------------------------------------------------------------
# نرمال‌سازی
# ---------------------------------------------------------------------------

# حروف مشابهی که معمولاً برای دور زدن فیلتر به‌جای شکل فارسی می‌نشیند.
_SIMILAR_LETTERS = {
    "ي": "ی", "ى": "ی", "ئ": "ی",
    "ك": "ک", "ڪ": "ک",
    "ة": "ه", "ۀ": "ه", "ھ": "ه",
    "أ": "ا", "إ": "ا", "ٱ": "ا",
    "ؤ": "و", "ٶ": "و", "ۉ": "و", "ۇ": "و",
}

# ارقام عربی/فارسی را NFKC به ASCII تبدیل نمی‌کند؛ دستی نگاشت می‌شود تا
# «س۶س» → «س6س» با کلاس جانشینی الگوی سخت‌گیر گرفته شود.
_ARABIC_DIGITS = {chr(0x0660 + i): str(i) for i in range(10)}
_ARABIC_DIGITS.update({chr(0x06F0 + i): str(i) for i in range(10)})

# نیم‌فاصله، جهت‌نماها، فاصلهٔ صفر، نرم‌خط و علائم نگارشی رایج → فاصله.
# ایموجی‌ها عمداً دست‌نخورده می‌مانند تا الگوهای ایموجی کار کنند.
_SEPARATOR_RX = re.compile(
    "["
    "\\u00ad\\u200b\\u200c\\u200d\\u200e\\u200f\\u202a-\\u202e\\u2060\\ufeff"
    "\\-_.,/\\\\;:!؟،؛|()\\[\\]{}<>+=*&^%$#@~\"'`«»…‹›“”‘’"
    "]+"
)

# کشیده «ـ» (tatweel) و اعراب عربی.
_DIACRITICS_RX = re.compile("[\\u0640\\u064b-\\u065f\\u0670]")

# هر چیزی که حرف یا رقم نیست (نسخهٔ «فقط حروف» برای س/ک/س با نماد بین حروف).
_NON_ALNUM_RX = re.compile(r"[\W_]+", re.UNICODE)


def _norm(value):
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", str(value)).lower()
    for src, dst in _SIMILAR_LETTERS.items():
        value = value.replace(src, dst)
    for src, dst in _ARABIC_DIGITS.items():
        value = value.replace(src, dst)
    value = _DIACRITICS_RX.sub("", value)
    value = _SEPARATOR_RX.sub(" ", value)
    return " ".join(value.split())


def _collapse(value):
    """جمع کردن حروف تکراری: «سسکس» و «بییییو» → «سکس» و «بیو»."""
    return re.sub(r"(.)\1+", r"\1", value)


def _variants(value):
    """نسخه‌های نرمال‌شدهٔ یک مقدار برای تطبیق، با برچسب «space»/«compact».

    space:   فاصله‌ها حفظ شده‌اند (متن عادی و بدون حروف تکراری).
    compact: فاصله‌ها/نمادها حذف شده‌اند (بدون‌فاصله و فقط حروف/ارقام).
    """
    base = _norm(value)
    if not base:
        return ()
    squashed = base.replace(" ", "")
    letters = _NON_ALNUM_RX.sub("", base)
    out = []
    seen = set()
    for kind, text in (
        ("space", base),
        ("space", _collapse(base)),
        ("compact", squashed),
        ("compact", _collapse(squashed)),
        ("compact", letters),
        ("compact", _collapse(letters)),
    ):
        if text and text not in seen:
            seen.add(text)
            out.append((kind, text))
    return tuple(out)


# ---------------------------------------------------------------------------
# الگوها
# ---------------------------------------------------------------------------

def _flex(term):
    """بین حروفِ واژه فقط فاصله/جداکننده مجاز است (هیچ حرف واقعی).

    روی نسخه‌های space شکل‌های «س ک س»/«س‌ک‌س» را می‌گیرد و روی نسخه‌های
    compact همان جست‌وجوی زیررشته‌ای محض است.
    """
    return re.compile(r"\s*".join(re.escape(ch) for ch in term))


# واژه‌ها و عبارت‌ها به شکل چسبیده نگه داشته می‌شوند؛ _flex فاصله‌های
# اختیاری بین حروف را خودش می‌سازد.
_WORD_TERMS = (
    # -- فهرست قبلی (حفظ رفتارهای فعلی) --
    "بیوچک", "چکبیو", "بیوگرافیچک",
    "بیوموچک", "بیوموببینید", "بیوموببین",
    "حالپی", "تمامسانسور", "حالمیدم", "حالمیذم", "فیلمپی", "پیوی",
    "خاله", "صیغه", "رایگان", "سکس", "سکسی", "پورن", "نود",
    "فیلترشکن", "شارژرایگان", "کانال", "پکیج", "ارزدیجیتال", "تتر",
    "پهلوی", "شاهزاده", "پرچمآمریکا", "دلباختهپهلوی", "رضاشاه",
    "محمدرضاشاه", "جانفدایمیهن", "فرزندایران",
    "فیلم",
    # -- افزوده‌های جدید --
    "بیوگرافی",
    "زوری",
    "یکیبیاد",
    "خانوم",
    "پسر",
    "دختر",
)
_WORD_PATTERNS = tuple((term, _flex(term)) for term in _WORD_TERMS)

# «گروه»: استثنای «گروه‌بان»/«گروهبان» تا نام واقعی گرفتار نشود؛ بقیهٔ
# شکل‌ها («گروه سکسی»، «گ رو ه») همچنان گرفته می‌شوند.
_WORD_PATTERNS += (
    ("گروه", re.compile(r"گ\s*ر\s*و\s*ه(?!\s*بان)")),
)

# پل «بیو … فیلم/لینک/چک/ببین» روی متنِ فاصله‌حفظ‌شده (رفتار قبلی).
_BRIDGE_PATTERNS = tuple(
    (p.pattern, p) for p in (
        re.compile(r"بیو.*(?:فیلم|لینک|چک|ببین)"),
    )
)

# عبارت‌های لاتین با مرز کلمه (رفتار قبلی pv/vpn).
_LATIN_BOUNDED = tuple(
    (p.pattern, p) for p in (
        re.compile(r"\bpv\b", re.IGNORECASE),
        re.compile(r"\bvpn\b", re.IGNORECASE),
    )
)

# الگوهای «سخت‌گیر» برای سکس/بیوگرافی: جانشینی حروف رایج
# (ث↔س، گ/ق/6/k ↔ ک) روی همهٔ نسخه‌ها (فقط حروف، نه متن کامل).
# انتهای «بیوگراف(ی)?» به‌کلمهٔ بعدی نمی‌چسبد تا «بیوکرافت» گرفتار نشود.
_STRICT_ANY = tuple(
    (p.pattern, p) for p in (
        re.compile(r"[سث][کگق6k][سث][ی]?"),
        # «ا» و «ی» اختیاری برای شکل‌های حذف‌حرفی (بیوگرفی، بیوگراف)،
        # ولی انتها نباید به کلمهٔ دیگری بچسبد («بیوکرافت» مجاز می‌ماند).
        re.compile(r"بیو[گکق]را?فی?(?![\w])"),
    )
)

# نسخهٔ لاتین سکس/بیوگرافی: با مرز کلمه روی متن عادی، آزاد روی compact
# تا «s e x» و «𝕤𝕖𝕩» هم گرفته شوند.
_STRICT_LATIN_BOUNDED = tuple(
    (p.pattern, p) for p in (
        re.compile(r"\bse+x[yi]?\b", re.IGNORECASE),
        re.compile(r"\bbiograph[yi]\b", re.IGNORECASE),
    )
)
_STRICT_LATIN_LOOSE = tuple(
    (p.pattern, p) for p in (
        re.compile(r"se+x[yi]?", re.IGNORECASE),
        re.compile(r"biograph[yi]", re.IGNORECASE),
    )
)

# ایموجی‌های تبلیغاتی — روی متن عادی و نسخهٔ بدون تکرار.
_EMOJI_TERMS = (
    "🔞", "💦", "🌈", "👄", "💋", "🤤", "😰", "🥵", "🍑",
)


def display_name(user):
    return format_user(user)


def reason(user):
    """اگر نام/آیدی کاربر تبلیغاتی باشد، توصیف الگوی ممنوع را برمی‌گرداند."""
    username_variants = _variants(getattr(user, "username", None))
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    name_variants = _variants(f"{first} {last}".strip())
    for variants in (username_variants, name_variants):
        if not variants:
            continue
        spaced = tuple(text for kind, text in variants if kind == "space")
        compact = tuple(text for kind, text in variants if kind == "compact")
        for value in spaced:
            for emoji in _EMOJI_TERMS:
                if emoji in value:
                    return emoji
            for label, pattern in _BRIDGE_PATTERNS:
                if pattern.search(value):
                    return label
            for label, pattern in _LATIN_BOUNDED + _STRICT_LATIN_BOUNDED:
                if pattern.search(value):
                    return label
        for value in spaced + compact:
            for term, pattern in _WORD_PATTERNS:
                if pattern.search(value):
                    return term
            for label, pattern in _STRICT_ANY:
                if pattern.search(value):
                    return label
        for value in compact:
            for label, pattern in _STRICT_LATIN_LOOSE:
                if pattern.search(value):
                    return label
    return None
