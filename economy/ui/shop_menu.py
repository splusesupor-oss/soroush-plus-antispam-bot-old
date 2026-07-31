"""🛒 بخش «فروشگاه» — مستقل از بخش موجودی.

فعلاً فقط زیرساخت: فهرست آیتم‌ها و خرید. افزودن آیتم جدید هیچ تغییری
در این فایل لازم ندارد؛ کافی است با ``economy.shop.add_item`` ثبت شود و
خودکار در فهرست و خرید ظاهر می‌شود.
"""
import time

import economy
from economy.ui.formatting import fa, spans_for

COMMAND = "فروشگاه"
SESSION_TIMEOUT = 180

MENU_LIST = "1"
MENU_BUY = "2"
MENU_CLOSE = "0"

_COIN_NAMES = {
    economy.BRONZE: "برنز",
    economy.SILVER: "نقره",
    economy.GOLD: "طلا",
}

_SESSIONS = {}


def normalize(text):
    value = str(text or "")
    for source, target in (("\u200c", " "), ("\u200f", ""), ("\u200e", ""),
                           ("ي", "ی"), ("ك", "ک")):
        value = value.replace(source, target)
    return " ".join(value.split())


def is_command(text):
    return normalize(text) == COMMAND


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


def open_session(chat_id, user_id, step="menu"):
    _prune()
    _SESSIONS[_key(chat_id, user_id)] = {"step": step, "at": time.monotonic()}


def close_session(chat_id, user_id):
    return _SESSIONS.pop(_key(chat_id, user_id), None) is not None


def session(chat_id, user_id):
    _prune()
    return _SESSIONS.get(_key(chat_id, user_id))


def reset_all():
    _SESSIONS.clear()


# ---------------------------------------------------------------------------
# متن‌ها
# ---------------------------------------------------------------------------
def render_menu(chat_id, user_id):
    balance = economy.get_balance(chat_id, user_id)
    header = "🛒 فروشگاه"
    count = len(economy.shop.list_items())
    text = (
        f"{header}\n\n"
        f"موجودی شما:\n"
        f"🥉 {fa(balance[economy.BRONZE])} | "
        f"🥈 {fa(balance[economy.SILVER])} | "
        f"🥇 {fa(balance[economy.GOLD])}\n"
        f"💎 ارزش کل: {fa(balance['total_coin_value'])}\n\n"
        f"آیتم‌های موجود: {fa(count)}\n\n"
        "برای انتخاب، شمارهٔ گزینه را بفرستید:\n\n"
        "۱) لیست آیتم‌ها\n"
        "۲) خرید\n"
        "۰) بستن"
    )
    return text, spans_for(text, [header, "💎 ارزش کل:"])


def render_items():
    items = economy.shop.list_items()
    header = "📦 لیست آیتم‌ها"
    if not items:
        text = (
            f"{header}\n\n"
            "هنوز آیتمی به فروشگاه اضافه نشده است.\n"
            "به‌زودی آیتم‌های جدید اضافه می‌شوند."
        )
        return text, spans_for(text, [header])

    lines = [header, ""]
    for item in items:
        stock = item.get("stock")
        stock_text = ""
        if stock is not None:
            stock_text = (f"\n📦 موجودی: {fa(stock)}" if stock > 0
                          else "\n📦 ناموجود")
        description = f"\n{item['description']}" if item.get("description") \
            else ""
        lines.append(
            f"🔖 {item['title']}\n"
            f"🆔 {item['id']}\n"
            f"💵 {fa(item['price'])} {_COIN_NAMES.get(item['coin_type'], '')}"
            f"{description}{stock_text}"
        )
    text = "\n\n".join(lines)
    return text, spans_for(text, [header])


def buy_prompt():
    items = economy.shop.list_items()
    if not items:
        return (
            "🛒 خرید\n\n"
            "هنوز آیتمی برای خرید وجود ندارد."
        )
    ids = "\n".join(f"• {item['id']} — {item['title']}" for item in items)
    return (
        "🛒 خرید\n\n"
        "شناسهٔ آیتم را بفرستید:\n\n"
        f"{ids}\n\n"
        "برای لغو، ۰ بفرستید."
    )


def do_buy(chat_id, user_id, item_id, *, reference=None):
    try:
        item, balance = economy.shop.buy(chat_id, user_id, item_id,
                                         reference=reference)
    except economy.shop.ShopError as error:
        return False, f"❌ {error}"
    return True, (
        f"✅ «{item['title']}» خریداری شد.\n\n"
        f"💵 پرداخت: {fa(item['price'])} "
        f"{_COIN_NAMES.get(item['coin_type'], '')}\n\n"
        f"موجودی شما:\n"
        f"🥉 {fa(balance[economy.BRONZE])} | "
        f"🥈 {fa(balance[economy.SILVER])} | "
        f"🥇 {fa(balance[economy.GOLD])}\n"
        f"💎 ارزش کل: {fa(balance['total_coin_value'])}"
    )
