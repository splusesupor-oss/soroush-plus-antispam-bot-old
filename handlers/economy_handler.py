"""💰 هندلر اقتصاد — تنها نقطهٔ اتصال اقتصاد به ربات.

دو بخش مستقل:
    «موجودی»  → منوی واحد شامل همهٔ قابلیت‌های اقتصاد
    «فروشگاه» → بخش جدا برای لیست و خرید

هیچ قابلیتی دستور جداگانه ندارد. این فایل هیچ بازی‌ای را import نمی‌کند
و هرگز مستقیماً به دیتابیس اقتصاد دست نمی‌زند؛ همه چیز از راه API.
"""
from splusthon.tl.types import MessageEntityBlockquote, MessageEntityBold

import economy
from economy.ui import balance_menu, shop_menu

CANCEL = "0"


def _entities(spans):
    built = []
    for kind, offset, length in spans:
        if kind == "bold":
            built.append(MessageEntityBold(offset=offset, length=length))
        elif kind == "blockquote":
            built.append(MessageEntityBlockquote(offset=offset,
                                                 length=length))
    return built


def _log(logger, message):
    if logger is not None:
        try:
            logger.log_info(message)
        except Exception:
            pass


def _log_error(logger, message):
    if logger is not None:
        try:
            logger.log_error(message)
        except Exception:
            pass


async def _send(event, payload):
    """``payload`` یا رشته است یا ``(text, spans)``."""
    if isinstance(payload, tuple):
        text, spans = payload
        await event.reply(text, formatting_entities=_entities(spans))
    else:
        await event.reply(payload)


async def _reply_to_user_id(event):
    """شناسهٔ کاربری که روی پیامش ریپلای شده."""
    try:
        if not getattr(event, "reply_to", None):
            return None, None
        message = await event.get_reply_message()
        if message is None:
            return None, None
        sender = await message.get_sender()
        if sender is None:
            return None, None
        name = " ".join(
            str(part).strip() for part in
            (getattr(sender, "first_name", None),
             getattr(sender, "last_name", None))
            if part and str(part).strip()
        ).strip()
        username = getattr(sender, "username", None)
        return getattr(sender, "id", None), (name or (f"@{username}"
                                                      if username else None))
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# بخش موجودی
# ---------------------------------------------------------------------------
async def _handle_balance_step(bot, event, chat_id, user_id, sender, text,
                               logger):
    state = balance_menu.session(chat_id, user_id)
    if state is None:
        return False
    choice = balance_menu._english(text)

    # --- مرحلهٔ دریافت مقدار انتقال ---
    if state["step"] == "transfer":
        if choice == CANCEL:
            balance_menu.close_session(chat_id, user_id)
            await _send(event, "لغو شد.")
            return True
        amount = balance_menu.parse_transfer_amount(text)
        if amount is None:
            return False        # عدد نیست: پیام عادی، منو دست‌نخورده می‌ماند

        target_id, target_name = await _reply_to_user_id(event)
        if target_id is None:
            await _send(event, "❌ باید روی پیام کاربر مقصد ریپلای کنید.")
            return True
        if str(target_id) == str(user_id):
            await _send(event, "❌ انتقال به خودتان ممکن نیست.")
            return True

        coin_type = state["coin"]
        reference = (f"transfer:{chat_id}:{user_id}:{target_id}:"
                     f"{coin_type}:{amount}:{event.message.id}")
        ok, message = balance_menu.do_transfer(
            user_id, target_id, coin_type, amount, reference=reference)
        if ok and target_name:
            economy.set_name(target_id, target_name)
        balance_menu.close_session(chat_id, user_id)
        await _send(event, message)
        _log(logger, f"ECONOMY TRANSFER chat_id={chat_id} from={user_id} "
                     f"to={target_id} coin={coin_type} amount={amount} "
                     f"ok={ok}")
        return True

    # --- منوی اصلی ---
    if choice == CANCEL:
        balance_menu.close_session(chat_id, user_id)
        await _send(event, "بسته شد.")
        return True

    if choice == balance_menu.MENU_BRONZE_TO_SILVER:
        ok, message = balance_menu.do_convert_bronze(user_id)
        await _send(event, message)
        _log(logger, f"ECONOMY CONVERT bronze->silver user_id={user_id} "
                     f"ok={ok}")
        return True

    if choice == balance_menu.MENU_SILVER_TO_GOLD:
        ok, message = balance_menu.do_convert_silver(user_id)
        await _send(event, message)
        _log(logger, f"ECONOMY CONVERT silver->gold user_id={user_id} ok={ok}")
        return True

    coin_type = balance_menu.coin_for_option(choice)
    if coin_type is not None:
        balance_menu.open_session(chat_id, user_id, step="transfer",
                                  coin=coin_type)
        await _send(event, balance_menu.transfer_prompt(coin_type, user_id))
        return True

    if choice == balance_menu.MENU_HISTORY:
        await _send(event, balance_menu.render_history(user_id))
        return True

    if choice == balance_menu.MENU_DAILY:
        ok, message = balance_menu.do_daily(user_id)
        await _send(event, message)
        _log(logger, f"ECONOMY DAILY user_id={user_id} granted={ok}")
        return True

    # هر متن دیگری: منو را نمی‌بندیم و پیام را هم مصرف نمی‌کنیم.
    return False


# ---------------------------------------------------------------------------
# بخش فروشگاه
# ---------------------------------------------------------------------------
async def _handle_shop_step(bot, event, chat_id, user_id, sender, text,
                            logger):
    state = shop_menu.session(chat_id, user_id)
    if state is None:
        return False
    choice = shop_menu.normalize(text)
    numeric = balance_menu._english(text)

    if state["step"] == "buy":
        if numeric == CANCEL:
            shop_menu.close_session(chat_id, user_id)
            await _send(event, "لغو شد.")
            return True
        reference = f"shop:{chat_id}:{user_id}:{choice}:{event.message.id}"
        ok, message = shop_menu.do_buy(user_id, choice, reference=reference)
        if ok:
            shop_menu.close_session(chat_id, user_id)
        await _send(event, message)
        _log(logger, f"ECONOMY SHOP BUY chat_id={chat_id} user_id={user_id} "
                     f"item={choice!r} ok={ok}")
        return True

    if numeric == CANCEL:
        shop_menu.close_session(chat_id, user_id)
        await _send(event, "بسته شد.")
        return True

    if numeric == shop_menu.MENU_LIST:
        await _send(event, shop_menu.render_items())
        return True

    if numeric == shop_menu.MENU_BUY:
        if not economy.shop.list_items():
            await _send(event, shop_menu.buy_prompt())
            return True
        shop_menu.open_session(chat_id, user_id, step="buy")
        await _send(event, shop_menu.buy_prompt())
        return True

    return False


# ---------------------------------------------------------------------------
# ورودی اصلی
# ---------------------------------------------------------------------------
async def handle(bot, event, chat_id, user_id, sender, text, logger=None):
    """``True`` یعنی پیام مصرف شد و هندلر اصلی نباید ادامه دهد."""
    # ۱) باز کردن بخش‌ها
    if balance_menu.is_command(text):
        shop_menu.close_session(chat_id, user_id)
        balance_menu.open_session(chat_id, user_id)
        display = _display_name(sender)
        if display:
            economy.set_name(user_id, display)
        await _send(event, balance_menu.render_menu(user_id))
        _log(logger, f"ECONOMY BALANCE MENU chat_id={chat_id} "
                     f"user_id={user_id}")
        return True

    if shop_menu.is_command(text):
        balance_menu.close_session(chat_id, user_id)
        shop_menu.open_session(chat_id, user_id)
        await _send(event, shop_menu.render_menu(user_id))
        _log(logger, f"ECONOMY SHOP MENU chat_id={chat_id} user_id={user_id}")
        return True

    # ۲) ادامهٔ گفتگوی باز
    try:
        if balance_menu.is_open(chat_id, user_id):
            if await _handle_balance_step(bot, event, chat_id, user_id,
                                          sender, text, logger):
                return True
        if shop_menu.is_open(chat_id, user_id):
            if await _handle_shop_step(bot, event, chat_id, user_id,
                                       sender, text, logger):
                return True
    except Exception as error:
        _log_error(logger, f"ECONOMY HANDLER FAILED chat_id={chat_id} "
                           f"user_id={user_id} error={error!r}")
        balance_menu.close_session(chat_id, user_id)
        shop_menu.close_session(chat_id, user_id)
        await _send(event, "❌ خطایی رخ داد؛ دوباره تلاش کنید.")
        return True
    return False


def _display_name(user):
    if user is None:
        return None
    parts = [
        str(part).strip() for part in
        (getattr(user, "first_name", None), getattr(user, "last_name", None))
        if part and str(part).strip()
    ]
    name = " ".join(parts).strip()
    if name:
        return name
    username = getattr(user, "username", None)
    return f"@{str(username).lstrip('@')}" if username else None


def reset_all():
    balance_menu.reset_all()
    shop_menu.reset_all()
