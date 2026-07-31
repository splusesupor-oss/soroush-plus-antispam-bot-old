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


async def _send(event, payload, logger=None):
    """``payload`` یا رشته است یا ``(text, spans)``.

    اگر سرور entityها را نپذیرد (که روی برخی نسخه‌های Soroush Plus رخ
    می‌دهد)، همان متن بدون قالب‌بندی فرستاده می‌شود. قالب‌بندی یک تزئین
    است و نباید باعث شود کاربر «هیچ خروجی» ببیند.
    """
    if not isinstance(payload, tuple):
        await event.reply(payload)
        return

    text, spans = payload
    try:
        await event.reply(text, formatting_entities=_entities(spans))
    except Exception as error:
        _log_error(logger,
                   "ECONOMY SEND WITH ENTITIES FAILED -> retrying plain "
                   f"error={error!r}")
        await event.reply(text)


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
            await _send(event, "لغو شد.", logger)
            return True
        amount = balance_menu.parse_transfer_amount(text)
        if amount is None:
            return False        # عدد نیست: پیام عادی، منو دست‌نخورده می‌ماند

        target_id, target_name = await _reply_to_user_id(event)
        if target_id is None:
            await _send(event, "❌ باید روی پیام کاربر مقصد ریپلای کنید.", logger)
            return True
        if str(target_id) == str(user_id):
            await _send(event, "❌ انتقال به خودتان ممکن نیست.", logger)
            return True

        coin_type = state["coin"]
        reference = (f"transfer:{chat_id}:{user_id}:{target_id}:"
                     f"{coin_type}:{amount}:{event.message.id}")
        ok, message = balance_menu.do_transfer(
            chat_id, user_id, target_id, coin_type, amount,
            reference=reference)
        if ok and target_name:
            economy.set_name(chat_id, target_id, target_name)
        balance_menu.close_session(chat_id, user_id)
        await _send(event, message, logger)
        _log(logger, f"ECONOMY TRANSFER chat_id={chat_id} from={user_id} "
                     f"to={target_id} coin={coin_type} amount={amount} "
                     f"ok={ok}")
        return True

    # --- منوی اصلی ---
    if choice == CANCEL:
        balance_menu.close_session(chat_id, user_id)
        await _send(event, "بسته شد.", logger)
        return True

    if choice == balance_menu.MENU_BRONZE_TO_SILVER:
        ok, message = balance_menu.do_convert_bronze(chat_id, user_id)
        await _send(event, message, logger)
        _log(logger, f"ECONOMY CONVERT bronze->silver user_id={user_id} "
                     f"ok={ok}")
        return True

    if choice == balance_menu.MENU_SILVER_TO_GOLD:
        ok, message = balance_menu.do_convert_silver(chat_id, user_id)
        await _send(event, message, logger)
        _log(logger, f"ECONOMY CONVERT silver->gold user_id={user_id} ok={ok}")
        return True

    coin_type = balance_menu.coin_for_option(choice)
    if coin_type is not None:
        balance_menu.open_session(chat_id, user_id, step="transfer",
                                  coin=coin_type)
        await _send(event, balance_menu.transfer_prompt(chat_id, coin_type, user_id),
                    logger)
        return True

    if choice == balance_menu.MENU_HISTORY:
        await _send(event, balance_menu.render_history(chat_id, user_id), logger)
        return True

    if choice == balance_menu.MENU_DAILY:
        ok, message = balance_menu.do_daily(chat_id, user_id)
        await _send(event, message, logger)
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
            await _send(event, "لغو شد.", logger)
            return True
        reference = f"shop:{chat_id}:{user_id}:{choice}:{event.message.id}"
        ok, message = shop_menu.do_buy(chat_id, user_id, choice, reference=reference)
        if ok:
            shop_menu.close_session(chat_id, user_id)
        await _send(event, message, logger)
        _log(logger, f"ECONOMY SHOP BUY chat_id={chat_id} user_id={user_id} "
                     f"item={choice!r} ok={ok}")
        return True

    if numeric == CANCEL:
        shop_menu.close_session(chat_id, user_id)
        await _send(event, "بسته شد.", logger)
        return True

    if numeric == shop_menu.MENU_LIST:
        await _send(event, shop_menu.render_items(), logger)
        return True

    if numeric == shop_menu.MENU_BUY:
        if not economy.shop.list_items():
            await _send(event, shop_menu.buy_prompt(), logger)
            return True
        shop_menu.open_session(chat_id, user_id, step="buy")
        await _send(event, shop_menu.buy_prompt(), logger)
        return True

    return False


# ---------------------------------------------------------------------------
# ورودی اصلی
# ---------------------------------------------------------------------------
async def handle(bot, event, chat_id, user_id, sender, text, logger=None):
    """``True`` یعنی پیام مصرف شد و هندلر اصلی نباید ادامه دهد."""
    # --- ردیابی ورود ---------------------------------------------------
    # هر پیامی که «شبیه» دستور اقتصاد است اینجا لاگ می‌شود، حتی اگر تطبیق
    # نکند. با این لاگ می‌توان فهمید پیام اصلاً به هندلر رسیده یا نه، و
    # اگر رسیده چرا تطبیق نکرده است.
    normalized = balance_menu.normalize(text)
    if normalized in {"موجودی", "فروشگاه"} or balance_menu.is_open(
            chat_id, user_id) or shop_menu.is_open(chat_id, user_id):
        _log(logger,
             "ECONOMY HANDLER ENTER "
             f"chat_id={chat_id} user_id={user_id} "
             f"raw_text={text!r} normalized={normalized!r} "
             f"balance_open={balance_menu.is_open(chat_id, user_id)} "
             f"shop_open={shop_menu.is_open(chat_id, user_id)}")

    # ۱) باز کردن بخش‌ها
    if balance_menu.is_command(text):
        try:
            shop_menu.close_session(chat_id, user_id)
            balance_menu.open_session(chat_id, user_id)
            display = _display_name(sender)
            if display:
                economy.set_name(chat_id, user_id, display)

            # مقدار خوانده‌شده از دیتابیس پیش از ارسال لاگ می‌شود تا اگر
            # پیام نرسید، بدانیم مشکل از خواندن است یا از ارسال.
            balance = economy.get_balance(chat_id, user_id)
            _log(logger,
                 "ECONOMY BALANCE READ "
                 f"chat_id={chat_id} user_id={user_id} "
                 f"bronze={balance[economy.BRONZE]} "
                 f"silver={balance[economy.SILVER]} "
                 f"gold={balance[economy.GOLD]} "
                 f"total_coin_value={balance['total_coin_value']} "
                 f"db_file={economy.storage.DATA_FILE}")

            payload = balance_menu.render_menu(chat_id, user_id)
            _log(logger,
                 "ECONOMY BALANCE RENDERED "
                 f"chat_id={chat_id} user_id={user_id} "
                 f"text_len={len(payload[0])} entities={len(payload[1])}")

            await _send(event, payload, logger)
            _log(logger, f"ECONOMY BALANCE MENU SENT chat_id={chat_id} "
                         f"user_id={user_id}")
        except Exception as error:
            # هیچ خطایی بی‌صدا نمی‌ماند: بدون این، شکست ارسال یا رندر
            # باعث می‌شد کاربر «هیچ خروجی» ببیند و لاگی هم نباشد.
            import traceback
            _log_error(logger,
                       "ECONOMY BALANCE MENU FAILED "
                       f"chat_id={chat_id} user_id={user_id} "
                       f"error={error!r}\n{traceback.format_exc()}")
            try:
                await event.reply(f"❌ خطا در نمایش موجودی: {error}")
            except Exception as reply_error:
                _log_error(logger,
                           "ECONOMY BALANCE FALLBACK REPLY FAILED "
                           f"chat_id={chat_id} error={reply_error!r}")
        return True

    if shop_menu.is_command(text):
        try:
            balance_menu.close_session(chat_id, user_id)
            shop_menu.open_session(chat_id, user_id)
            balance = economy.get_balance(chat_id, user_id)
            _log(logger,
                 "ECONOMY SHOP READ "
                 f"chat_id={chat_id} user_id={user_id} "
                 f"bronze={balance[economy.BRONZE]} "
                 f"total_coin_value={balance['total_coin_value']} "
                 f"items={len(economy.shop.list_items())}")
            await _send(event, shop_menu.render_menu(chat_id, user_id), logger)
            _log(logger, f"ECONOMY SHOP MENU SENT chat_id={chat_id} "
                         f"user_id={user_id}")
        except Exception as error:
            import traceback
            _log_error(logger,
                       "ECONOMY SHOP MENU FAILED "
                       f"chat_id={chat_id} user_id={user_id} "
                       f"error={error!r}\n{traceback.format_exc()}")
            try:
                await event.reply(f"❌ خطا در نمایش فروشگاه: {error}")
            except Exception as reply_error:
                _log_error(logger,
                           "ECONOMY SHOP FALLBACK REPLY FAILED "
                           f"chat_id={chat_id} error={reply_error!r}")
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
        await _send(event, "❌ خطایی رخ داد؛ دوباره تلاش کنید.", logger)
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
