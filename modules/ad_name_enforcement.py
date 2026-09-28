"""اجرای مجازات «نام تبلیغاتی» — مشترک بین سه مسیر پیام/ورود/تغییر نام.

جریانِ یکسانِ قبلی در ``handlers/message_handler.py`` بود (فقط روی پیامِ
دریافتی می‌تاخت). این ماژول همان جریان را بدون تغییر در سیاست بیرون می‌دهد
تا رخدادهای ورود عضو و تغییر نام هم از همان استفاده کنند:

1. تشخیص با «ad_name_detector.reason» (سیستم موجود، تقویت‌شده)
2. پاکسازی پیام‌های کاربر با «همان» امکانات فعلی سیستم:
   - صف حذف روی آی‌دی‌های ردیابِ درون‌حافظه‌ای (message_tracker + spam_history)
   - اگر ردیاب چیزی نداشت (مثلاً ورود بدون پیام دیده‌شده)، یک جاروی
     محدودِ تاریخچه در پس‌زمینه با همان سقفِ جاروی اسپم (۳۰۰ پیام اخیر)
3. صف مجازات از طریق moderation_queue → AdminActions.ban_user که خودش
   بر اساس «تغییر مجازات» هر گروه، بن یا سکوت دائمی اعمال می‌کند
4. اعلان در گروه فقط بعد از موفقیتِ مجازات + لاگ و دلیل مثل قبل

محدودیت API فعلی صادقانه نگه داشته می‌شود: «بن» (EditBanned) پیام‌های
قدیمی را خودکار پاک نمی‌کند و «حذف تاریخچهٔ عضو» در سطح API در دسترس
نیست؛ بنابراین فقط پیام‌هایی پاک می‌شوند که ردیاب زمان‌اجرا دیده یا در
نزدیک‌ترین صفحهٔ تاریخچهٔ گروه (سقف ۳۰۰ پیام) پیدا شوند.
"""
import asyncio as _asyncio

from modules import ad_name_detector, message_tracker, punishment_mode
from modules.group_id import normalize_group_id
from modules.spam_history import get_message_ids

# سقف جاروی پس‌زمینه‌ای تاریخچه — عمداً با SPAM_HISTORY_SWEEP_LIMIT هندلر
# یکی است تا رفتار پاکسازی با مسیر اسپم فرق نکند.
_SWEEP_LIMIT = 300


def _punish_key(chat_id, user_id):
    """کلید رخداد مجازات — باید با handlers.message_handler._punishment_key
    یکی بماند تا قفلِ تک‌رخدادی بین دو مسیر مشترک بماند."""
    return f"{normalize_group_id(chat_id)}:{user_id}"


def _queue_deletes(bot, chat_id, message_ids, *, priority=1):
    """حذف از طریق همان صف حذف موجود؛ اگر نبود، fallback مثل مسیر اسپم."""
    queue = getattr(bot, "message_delete_queue", None)
    if queue is not None:
        return queue.enqueue(chat_id, list(message_ids), priority=priority)

    async def fallback():
        try:
            await bot.client.delete_messages(chat_id, list(message_ids))
        except Exception as error:
            bot.logger.log_error(
                f"AD NAME DELETE FALLBACK FAILED chat_id={chat_id} error={error!r}"
            )
    return _asyncio.get_running_loop().create_task(fallback())


async def _same_sender(message, user_id):
    sender_id = getattr(message, "sender_id", None)
    if sender_id is None:
        from_id = getattr(message, "from_id", None)
        sender_id = getattr(from_id, "user_id", None)
    if sender_id is None:
        get_sender = getattr(message, "get_sender", None)
        if callable(get_sender):
            sender = await get_sender()
            sender_id = getattr(sender, "id", None)
    return sender_id is not None and str(sender_id) == str(user_id)


def _running_sweeps(bot):
    sweeps = getattr(bot, "_ad_name_sweeps", None)
    if sweeps is None:
        sweeps = bot._ad_name_sweeps = set()
    return sweeps


async def _history_sweep(bot, chat_id, user_id, key, source):
    """بازیابی پیام‌های کاربر از صفحهٔ اخیر تاریخچه — فقط وقتی ردیاب خالی است.

    محدود به آخرین ۳۰۰ پیام گروه (مثل جاروی اسپم)؛ پیام‌های قدیمی‌تر همچنان
    طبق محدودیت API پاک نمی‌شوند و این در لاگ هم نوشته می‌شود.
    """
    ids = set()
    scanned = 0
    try:
        for attempt in range(2):
            try:
                async for message in bot.client.iter_messages(
                        chat_id, limit=_SWEEP_LIMIT, wait_time=1):
                    scanned += 1
                    if not await _same_sender(message, user_id):
                        continue
                    message_id = getattr(message, "id", None)
                    if isinstance(message_id, int) and message_id > 0:
                        ids.add(message_id)
            except _asyncio.CancelledError:
                raise
            except Exception as error:
                wait = getattr(error, "seconds", None)
                if wait and attempt == 0:
                    delay = min(max(float(wait), 1.0), 30.0)
                    bot.logger.log_error(
                        "AD NAME HISTORY SWEEP FLOODWAIT "
                        f"chat_id={chat_id} user_id={user_id} wait_s={delay:.1f}"
                    )
                    await _asyncio.sleep(delay)
                    continue
                bot.logger.log_error(
                    "AD NAME HISTORY SWEEP FAILED "
                    f"chat_id={chat_id} user_id={user_id} scanned={scanned} "
                    f"error={error!r}"
                )
                break
            else:
                break
        if ids:
            _queue_deletes(bot, chat_id, sorted(ids))
        bot.logger.log_info(
            "AD NAME HISTORY SWEEP COMPLETE "
            f"chat_id={chat_id} user_id={user_id} source={source} "
            f"scanned={scanned} found={len(ids)} limit={_SWEEP_LIMIT}"
        )
    finally:
        _running_sweeps(bot).discard(key)


def _start_history_sweep(bot, chat_id, user_id, *, source):
    key = (normalize_group_id(chat_id), str(user_id))
    sweeps = _running_sweeps(bot)
    if key in sweeps:
        return None
    client = getattr(bot, "client", None)
    if not callable(getattr(client, "iter_messages", None)):
        bot.logger.log_error(
            "AD NAME HISTORY SWEEP UNAVAILABLE "
            f"chat_id={chat_id} user_id={user_id}"
        )
        return None
    sweeps.add(key)
    task = _asyncio.get_running_loop().create_task(
        _history_sweep(bot, chat_id, user_id, key, source),
        name="ad-name:sweep",
    )
    return task


def _purge_user_messages(bot, chat_id, user_id, *, event=None, message_id=None,
                         source="message", duplicate=False):
    """هر پیامی که امکانات فعلی از این کاربر می‌دانند → صف حذف؛ تعداد برگشت.

    اگر ردیاب خالی باشد و رخداد تکراری هم نباشد، جاروی پس‌زمینه فعال می‌شود
    (ورود عضو/تغییر نام بدون پیامِ دیده‌شده).
    """
    if message_id is None and event is not None:
        message_id = getattr(getattr(event, "message", None), "id", None)
    ids = {
        message_id_ for message_id_ in
        message_tracker.spam_snapshot(chat_id, user_id, message_id)
        if isinstance(message_id_, int) and message_id_ > 0
    }
    try:
        ids.update(
            message_id_ for message_id_ in (get_message_ids(chat_id, user_id) or ())
            if isinstance(message_id_, int) and message_id_ > 0
        )
    except Exception:
        pass
    if ids:
        _queue_deletes(bot, chat_id, sorted(ids))
        bot.logger.log_info(
            "AD NAME PURGE QUEUED "
            f"chat_id={chat_id} user_id={user_id} source={source} "
            f"ids={len(ids)} duplicate={duplicate}"
        )
    elif not duplicate:
        _start_history_sweep(bot, chat_id, user_id, source=source)
    return len(ids)


def _notice_entities(shown_name):
    try:
        from splusthon.tl.types import MessageEntityBold, MessageEntityBlockquote
    except Exception:
        return None
    try:
        name_start = len("⚠️ کاربر\n".encode("utf-16-le")) // 2
        name_len = len(shown_name.encode("utf-16-le")) // 2
        bold_len = len("⚠️ کاربر".encode("utf-16-le")) // 2
        return [
            MessageEntityBold(offset=0, length=bold_len),
            MessageEntityBlockquote(offset=name_start, length=name_len),
        ]
    except Exception:
        return None


async def _notify_success(bot, event, chat_id, shown_name, notice):
    """اعلان بعد از موفقیت مجازات؛ با event مثل قبل reply می‌کند و بدون
    event (ورود/تغییر نام) پیام عادی گروه است. هر خطا فقط لاگ می‌شود."""
    entities = _notice_entities(shown_name)
    kwargs = {"formatting_entities": entities} if entities else {}

    def _capture(sent):
        try:
            from modules.notice_cleanup import capture_sent
            capture_sent(bot, chat_id, sent)
        except Exception:
            pass

    try:
        sender3 = getattr(bot, "outgoing_sender", None)
        if event is not None and sender3 is not None:
            try:
                sender3.enqueue_reply(
                    event, notice, on_done=_capture, **kwargs)
            except Exception:
                sender3.enqueue_reply(event, notice, on_done=_capture)
            return
        if event is not None:
            try:
                sent = await event.reply(notice, **kwargs)
            except Exception:
                sent = await event.reply(notice)
            _capture(sent)
            return
        if sender3 is not None:
            try:
                sender3.enqueue_send(
                    chat_id, notice, on_done=_capture, **kwargs)
            except Exception:
                sender3.enqueue_send(chat_id, notice, on_done=_capture)
            return
        try:
            sent = await bot.client.send_message(chat_id, notice, **kwargs)
        except Exception:
            sent = await bot.client.send_message(chat_id, notice)
        _capture(sent)
    except Exception as error:
        bot.logger.log_error(
            f"AD NAME NOTIFY FAILED chat_id={chat_id} error={error!r}"
        )


def enforce(bot, chat_id, user_id, sender, *, event=None, message_id=None,
            source="message", ad_reason=None):
    """تشخیص + پاکسازی پیام‌ها + صف مجازات + اعلان و لاگ.

    True یعنی رخداد (جدید یا تکراری) ثبت شد و جریان عادی پردازش باید
    متوقف شود؛ False یعنی نامی تبلیغاتی نیست. هیچ RPC ای در همین نقطه
    await نمی‌شود؛ همه چیز از صف‌های موجود عبور می‌کند.
    """
    if not ad_reason:
        ad_reason = ad_name_detector.reason(sender)
        if not ad_reason:
            return False
    punish_key = _punish_key(chat_id, user_id)
    if punish_key in bot.punished_users:
        # رخداد قبلاً ثبت شده، ولی پیام‌های قابل‌حذف (از جمله پیام‌هایی که
        # تا لحظهٔ اعمال مجازات فرستاده) همچنان باید پاک شوند.
        _purge_user_messages(
            bot, chat_id, user_id,
            event=event, message_id=message_id,
            source=source, duplicate=True,
        )
        bot.logger.log_info(
            "AD NAME INCIDENT DUPLICATE SKIPPED "
            f"chat_id={chat_id} user_id={user_id} source={source} "
            f"message_id={message_id}"
        )
        return True
    bot.punished_users.add(punish_key)
    shown_name = ad_name_detector.display_name(sender)
    # ۱) پاکسازی پیام‌های کاربر قبل از صدور مجازات
    purged_count = _purge_user_messages(
        bot, chat_id, user_id,
        event=event, message_id=message_id, source=source,
    )
    # ۲) متن اعلان (دقیقاً قالب قبلی؛ سکوت/اخراج طبق حالت مجازات گروه)
    if punishment_mode.is_mute(chat_id):
        ad_action_line = "به دلیل داشتن نام تبلیغاتی و لینک سکوت دائم شد."
    else:
        ad_action_line = "به دلیل داشتن نام تبلیغاتی و لینک اخراج شد."
    notice = "⚠️ کاربر\n" f"{shown_name}\n\n" f"{ad_action_line}"

    async def ad_name_ban_succeeded(_result):
        # اعلان عمداً بعد از موفقیت واقعیِ مجازات و فقط برای همین رخداد.
        await _notify_success(bot, event, chat_id, shown_name, notice)
        bot.logger.log_info(
            "AD NAME BAN FINISHED "
            f"chat_id={chat_id} user_id={user_id} source={source} "
            f"reason={ad_reason!r} notification_sent=True"
        )

    async def ad_name_ban_failed(error):
        # شکست RPC نباید قفل درون‌حافظه‌ای رخداد را دائمی کند.
        bot.punished_users.discard(punish_key)
        bot.logger.log_error(
            "AD NAME BAN FAILED "
            f"chat_id={chat_id} user_id={user_id} source={source} error={error!r}"
        )

    queued = bot.moderation_queue.enqueue(
        chat_id,
        "ban",
        user_id=user_id,
        timeout_seconds=45,
        operation=lambda: bot.admin_actions.ban_user(
            chat_id, user_id, reason="نام تبلیغاتی",
            user=sender,
        ),
        on_success=ad_name_ban_succeeded,
        on_failure=ad_name_ban_failed,
    )
    if not queued:
        bot.punished_users.discard(punish_key)
        bot.logger.log_info(
            "AD NAME INCIDENT QUEUE DUPLICATE "
            f"chat_id={chat_id} user_id={user_id} source={source}"
        )
    else:
        bot.logger.log_info(
            "AD NAME BAN QUEUED "
            f"chat_id={chat_id} user_id={user_id} source={source} "
            f"name={shown_name!r} reason={ad_reason!r} "
            f"purged_ids={purged_count}"
        )
    return True
