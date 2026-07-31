"""👤 بخش «پروفایل» — ثبت اطلاعات، نمایش کارت و خرید آیتم‌ها.

دو مسیر دارد:

  ۱) کاربر تازه: «پروفایل» → اسم → شهر → سن → لقب (اختیاری) → کارت
  ۲) کاربر ثبت‌شده: «پروفایل» → مستقیم کارت + منو

همهٔ آیتم‌های قابل خرید (نشان، ستاره، لقب) *فقط* داخل بخش
«📦 لیست آیتم‌ها» نمایش داده می‌شوند و هیچ بخش جداگانه‌ای ندارند.

این ماژول فقط از API عمومی اقتصاد استفاده می‌کند و هیچ‌جا فایل دیتابیس
را مستقیماً باز نمی‌کند.
"""
import time

import economy
from economy import catalog, profiles
from economy.ui.formatting import fa_plain, spans_for, u16

COMMAND = "پروفایل"
SESSION_TIMEOUT = 300

STEP_MENU = "menu"
STEP_NAME = "name"
STEP_CITY = "city"
STEP_AGE = "age"
STEP_NICKNAME = "nickname"
STEP_BUY = "buy"
STEP_EDIT = "edit"
STEP_EDIT_VALUE = "edit_value"

MENU_ITEMS = "1"
MENU_BUY = "2"
MENU_EDIT = "3"
MENU_CLOSE = "0"

EDIT_NAME = "1"
EDIT_CITY = "2"
EDIT_AGE = "3"
EDIT_NICKNAME = "4"

_EDIT_FIELDS = {
    EDIT_NAME: ("name", "اسم"),
    EDIT_CITY: ("city", "شهر"),
    EDIT_AGE: ("age", "سن"),
    EDIT_NICKNAME: ("nickname", "لقب"),
}

BOX_TOP = "╔════════════════════╗"
BOX_BOTTOM = "╚════════════════════╝"

STAR_FULL = "★"
STAR_EMPTY = "☆"

_COIN_NAMES = {
    economy.BRONZE: "برنز",
    economy.SILVER: "نقره",
    economy.GOLD: "طلا",
}

_SESSIONS = {}

_DIGIT_MAP = {ord(p): str(i) for i, p in enumerate("۰۱۲۳۴۵۶۷۸۹")}
_DIGIT_MAP.update({ord(a): str(i) for i, a in enumerate("٠١٢٣٤٥٦٧٨٩")})


def _english(text):
    return str(text or "").translate(_DIGIT_MAP).strip()


def normalize(text):
    value = str(text or "")
    for source, target in (("\u200c", " "), ("\u200f", ""), ("\u200e", ""),
                           ("ي", "ی"), ("ك", "ک")):
        value = value.replace(source, target)
    return " ".join(value.split())


def is_command(text):
    return normalize(text) == COMMAND


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------
def _key(chat_id, user_id):
    return (str(chat_id), str(user_id))


def _prune():
    now = time.monotonic()
    for key, item in list(_SESSIONS.items()):
        if now - item["at"] > SESSION_TIMEOUT:
            del _SESSIONS[key]


def is_open(chat_id, user_id):
    _prune()
    return _key(chat_id, user_id) in _SESSIONS


def open_session(chat_id, user_id, step=STEP_MENU, **extra):
    _prune()
    session = {"step": step, "at": time.monotonic(), "draft": {}}
    session.update(extra)
    _SESSIONS[_key(chat_id, user_id)] = session
    return session


def close_session(chat_id, user_id):
    return _SESSIONS.pop(_key(chat_id, user_id), None) is not None


def session(chat_id, user_id):
    _prune()
    return _SESSIONS.get(_key(chat_id, user_id))


def touch(chat_id, user_id, step=None, **extra):
    state = session(chat_id, user_id)
    if state is None:
        return None
    state["at"] = time.monotonic()
    if step is not None:
        state["step"] = step
    state.update(extra)
    return state


def reset_all():
    _SESSIONS.clear()


# ---------------------------------------------------------------------------
# عنوان پویا
# ---------------------------------------------------------------------------
def display_username(sender):
    """``@username`` یا ``None``."""
    username = getattr(sender, "username", None)
    username = str(username).strip().lstrip("@") if username else ""
    return f"@{username}" if username else None


def display_name(sender):
    """نام نمایشی حساب (نام + نام خانوادگی)."""
    parts = [
        str(part).strip() for part in
        (getattr(sender, "first_name", None), getattr(sender, "last_name", None))
        if part and str(part).strip()
    ]
    return " ".join(parts).strip() or None


def build_title(profile, sender=None):
    """عنوان داخل کادر، طبق قوانین درخواست‌شده.

    اولویت: لقب ← یوزرنیم ← اسم نمایشی. اگر هیچ نشانی خریداری نشده
    باشد، هیچ ایموجی‌ای کنار عنوان نمی‌آید.
    """
    label = (profile.get("nickname") or "").strip()
    if not label:
        label = display_username(sender) or ""
    if not label:
        label = display_name(sender) or ""
    if not label:
        label = (profile.get("name") or "").strip()
    if not label:
        label = "کاربر"

    badges = [item for item in
              (catalog.get_badge(badge_id)
               for badge_id in profile.get("badges", []))
              if item]
    if not badges:
        return label
    emoji = badges[0]["emoji"]
    return f"{emoji} {label} {emoji}"


def build_stars(count):
    count = max(0, min(catalog.MAX_STARS, int(count or 0)))
    return STAR_FULL * count + STAR_EMPTY * (catalog.MAX_STARS - count)


# ---------------------------------------------------------------------------
# کارت پروفایل
# ---------------------------------------------------------------------------
def render_card(chat_id, user_id, sender=None):
    """کارت پروفایل، دقیقاً با همان چیدمان درخواست‌شده."""
    profile = profiles.get(chat_id, user_id)
    balance = economy.get_balance(chat_id, user_id)
    coin_profile = economy.get_profile(chat_id, user_id)
    rank = economy.get_rank(chat_id, user_id)

    title = build_title(profile, sender)
    name = (profile.get("name") or display_name(sender)
            or display_username(sender) or "—")
    nickname = (profile.get("nickname") or "").strip()
    badges = [item for item in
              (catalog.get_badge(badge_id)
               for badge_id in profile.get("badges", []))
              if item]
    badge_line = " ".join(item["emoji"] for item in badges) if badges \
        else "ندارد"
    city = profile.get("city") or "—"
    age = profile.get("age")
    age_line = f"{fa_plain(age)} سال" if age else "—"

    lines = [
        BOX_TOP,
        title,
        BOX_BOTTOM,
        "",
        f"👤 نام: {name}",
    ]
    if nickname:
        lines.append(f"🏷 لقب: {nickname}")
    lines += [
        "",
        "🛡 نشان‌ها:",
        badge_line,
        "",
        f"⭐ سطح: {build_stars(profile.get('stars', 0))}",
        "",
        f"🥉 برنز: {fa_plain(balance[economy.BRONZE])}",
        f"🥈 نقره: {fa_plain(balance[economy.SILVER])}",
        f"🥇 طلا: {fa_plain(balance[economy.GOLD])}",
        "",
        f"📍 شهر: {city}",
        f"🎂 سن: {age_line}",
        "",
        f"🎮 برد: {fa_plain(coin_profile.get('wins', 0))}",
        f"🏅 رتبه: {('#' + fa_plain(rank)) if rank else 'ندارد'}",
    ]
    text = "\n".join(lines)
    spans = spans_for(text, [title])
    spans += spans_for(text, ["👤 نام:", "🏷 لقب:", "🛡 نشان‌ها:", "⭐ سطح:",
                              "🥉 برنز:", "🥈 نقره:", "🥇 طلا:", "📍 شهر:",
                              "🎂 سن:", "🎮 برد:", "🏅 رتبه:"])
    return text, spans


def menu_block():
    return (
        "برای انتخاب، شمارهٔ گزینه را بفرستید:\n"
        "۱) 📦 لیست آیتم‌ها\n"
        "۲) 🛍 خرید آیتم\n"
        "۳) ✏️ ویرایش اطلاعات\n"
        "۰) بستن"
    )


def render_menu(chat_id, user_id, sender=None):
    """کارت پروفایل به‌همراه منوی گزینه‌ها."""
    card, spans = render_card(chat_id, user_id, sender)
    # کارت پیشوند متن نهایی است، پس offsetهای محاسبه‌شده دست‌نخورده
    # معتبر می‌مانند و نیازی به بازمحاسبه نیست.
    return f"{card}\n\n{menu_block()}", spans


# ---------------------------------------------------------------------------
# 📦 لیست آیتم‌ها — تنها جای نمایش آیتم‌های قابل خرید
# ---------------------------------------------------------------------------
def render_items(chat_id=None, user_id=None):
    """فهرست کامل آیتم‌ها؛ کل متن Bold است.

    آیتم‌هایی که کاربر دارد با ✅ علامت می‌خورند (اگر شناسه داده شود).
    """
    owned = set()
    stars_now = 0
    if chat_id is not None and user_id is not None:
        profile = profiles.get(chat_id, user_id)
        owned = set(profile["badges"]) | set(profile["titles"])
        stars_now = int(profile["stars"])

    def mark(item):
        if item["kind"] == catalog.KIND_STAR:
            return "✅ " if stars_now >= int(item["level"]) else ""
        return "✅ " if item["id"] in owned else ""

    lines = ["📦 لیست آیتم‌ها", ""]
    number = 0

    lines.append("🛡 نشان‌ها")
    for item in catalog.badges():
        number += 1
        lines.append(
            f"{mark(item)}{fa_plain(number)}) {item['emoji']} {item['name']}"
            f" — {fa_plain(item['price'])} {_COIN_NAMES[item['coin_type']]}"
        )

    lines += ["", "⭐ خرید سطح"]
    for item in catalog.stars():
        number += 1
        lines.append(
            f"{mark(item)}{fa_plain(number)}) {item['emoji']} {item['name']}"
            f" — {fa_plain(item['price'])} {_COIN_NAMES[item['coin_type']]}"
        )

    lines += ["", "🏷 خرید لقب اختصاصی",
              f"قیمت همه لقب‌ها: {fa_plain(catalog.TITLE_PRICE)} "
              f"{_COIN_NAMES[catalog.TITLE_COIN]}"]
    for item in catalog.titles():
        number += 1
        lines.append(
            f"{mark(item)}{fa_plain(number)}) {item['emoji']} {item['title']}"
        )

    lines += ["", "برای خرید، شمارهٔ آیتم را بفرستید."]
    text = "\n".join(lines)
    # کل بخش Bold است.
    return text, [("bold", 0, u16(text))]


def buy_prompt(chat_id=None, user_id=None):
    text, spans = render_items(chat_id, user_id)
    text = f"{text}\nبرای لغو، ۰ بفرستید."
    return text, [("bold", 0, u16(text))]


def do_buy(chat_id, user_id, text, *, reference=None):
    item = catalog.resolve(text)
    if item is None:
        return False, "❌ چنین آیتمی در فهرست نیست. شمارهٔ آیتم را بفرستید."
    try:
        item, balance, profile = profiles.buy(chat_id, user_id, item["id"],
                                              reference=reference)
    except profiles.ProfileError as error:
        return False, f"❌ {error}"

    if item["kind"] == catalog.KIND_BADGE:
        applied = f"🛡 نشان {item['emoji']} به پروفایل شما اضافه شد."
    elif item["kind"] == catalog.KIND_STAR:
        applied = f"⭐ سطح شما: {build_stars(profile.get('stars', 0))}"
    else:
        applied = f"🏷 لقب شما: {item['title']}"

    return True, (
        f"✅ «{item['label']}» خریداری شد.\n\n"
        f"{applied}\n\n"
        f"💵 پرداخت: {fa_plain(item['price'])} "
        f"{_COIN_NAMES[item['coin_type']]}\n\n"
        f"🥉 {fa_plain(balance[economy.BRONZE])} | "
        f"🥈 {fa_plain(balance[economy.SILVER])} | "
        f"🥇 {fa_plain(balance[economy.GOLD])}"
    )


# ---------------------------------------------------------------------------
# ثبت‌نام
# ---------------------------------------------------------------------------
PROMPT_NAME = ("👤 ثبت پروفایل\n\n"
               "اسم خود را بفرستید:")
PROMPT_CITY = "🏙 شهر خود را بفرستید:"
PROMPT_AGE = "🎂 سن خود را بفرستید:"
PROMPT_NICKNAME = ("🏷 لقب خود را بفرستید.\n"
                   "این مورد اختیاری است؛ برای رد شدن ۰ بفرستید.")

PROMPT_EDIT = (
    "✏️ ویرایش اطلاعات\n\n"
    "کدام مورد را ویرایش می‌کنید؟\n"
    "۱) اسم\n"
    "۲) شهر\n"
    "۳) سن\n"
    "۴) لقب\n"
    "۰) بازگشت"
)


def edit_prompt(field_label):
    return f"✏️ مقدار جدید «{field_label}» را بفرستید:"
