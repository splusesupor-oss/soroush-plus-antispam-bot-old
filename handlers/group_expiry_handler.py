"""⏳ هندلر مستقل «تاریخ انقضای گروه».

تنها نقطهٔ اتصال این قابلیت به ربات. هیچ state ای اینجا نگه داشته
نمی‌شود و هیچ ماژول بازی/حافظه/قفلی import نمی‌گردد.

مسیر پردازش کاملاً جداست و تطبیق دستور «دقیق» است، پس هیچ
``startswith`` عمومی‌ای نمی‌تواند این سه دستور را با چیز دیگری اشتباه
بگیرد.
"""
try:
    from splusthon.tl.types import MessageEntityBlockquote, MessageEntityBold
except ImportError:
    class MessageEntityBlockquote:
        def __init__(self, offset=0, length=0):
            self.offset = offset
            self.length = length
    class MessageEntityBold:
        def __init__(self, offset=0, length=0):
            self.offset = offset
            self.length = length

from modules.group_expiry import (
    EXPIRED_MESSAGE,
    build_confirmation,
    build_expired_message,
    build_remaining_message,
    due_groups,
    format_remaining,
    is_expired,
    mark_notified,
    match_command,
    match_remaining_command,
    seconds_left,
    set_expiry,
    update_title as update_expiry_title,
)
from modules.owner_check import is_global_owner

# پیامی که وقتی گروه منقضی است به غیرمالک نشان داده می‌شود.
EXPIRED_NOTICE = (
    "⛔ مدت زمان فعال بودن این گروه به پایان رسیده است.\n\n"
    "برای فعال‌سازی دوباره، مالک اصلی باید یکی از دستورهای "
    "«۵ روز»، «یک هفته»، «دو هفته» یا «یک ماه» را ارسال کند."
)

CHECK_INTERVAL_SECONDS = 20


def _entities(spans):
    """تبدیل span های خنثی به entity واقعی splusthon."""
    built = []
    for kind, offset, length in spans:
        if kind == "blockquote":
            built.append(MessageEntityBlockquote(offset=offset, length=length))
        elif kind == "bold":
            built.append(MessageEntityBold(offset=offset, length=length))
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


async def handle(bot, event, chat_id, sender, text, logger=None):
    """اگر پیام یکی از سه دستور انقضا باشد آن را پردازش می‌کند.

    ``True`` یعنی پیام مصرف شد و هندلر اصلی نباید ادامه دهد.
    """
    command = match_command(text)
    if command is None:
        return False

    # فقط مالک اصلی. برای بقیه هیچ پاسخی داده نمی‌شود تا این دستورها
    # برای کاربران عادی اصلاً وجود نداشته باشند.
    if not is_global_owner(sender):
        _log(logger, "GROUP EXPIRY DENIED "
                     f"chat_id={chat_id} user_id={getattr(sender, 'id', None)} "
                     f"command={command!r} reason=not_global_owner")
        return True

    title = getattr(await _safe_chat(event), "title", "") or ""
    result = set_expiry(chat_id, command, title=title)
    if result is None:
        _log_error(logger, f"GROUP EXPIRY SET FAILED chat_id={chat_id} "
                           f"command={command!r}")
        return True

    text_out, spans = build_confirmation(
        result["activated_at"], result["expires_at"])
    await event.reply(text_out, formatting_entities=_entities(spans))
    _log(logger, "GROUP EXPIRY SET "
                 f"chat_id={chat_id} command={command!r} days={result['days']} "
                 f"activated_at={result['activated_at'].isoformat()} "
                 f"expires_at={result['expires_at'].isoformat()}")
    return True


async def _safe_chat(event):
    try:
        return await event.get_chat()
    except Exception:
        return None


# پیام دسترسی برای دستور خبری «مهلت گروه».
REMAINING_DENIED = (
    "❌ فقط مالک یا ادمین گروه اجازه استفاده از این دستور را دارد"
)


def _remaining_allowed(chat_id, sender):
    """دسترسی «مهلت گروه»: مالک اصلی ربات، مالک گروه یا ادمین ثبت‌شده."""
    if is_global_owner(sender):
        return True
    try:
        from modules import admin_tools
        return bool(admin_tools.has_admin_permission(
            chat_id,
            getattr(sender, "id", None),
            (getattr(sender, "username", None) or "").lstrip("@"),
        ))
    except Exception:
        return False


def _stored_title(chat_id):
    """نام ذخیره‌شدهٔ گروه: اول groups.json، بعد رکورد انقضا."""
    try:
        from modules import group_storage
        data = group_storage.load_groups()
        key = group_storage._group_key(data, chat_id)
        group = data.get(key)
        if isinstance(group, dict):
            title = str(group.get("title") or "").strip()
            if title:
                return title
    except Exception:
        pass
    try:
        from modules.group_expiry import get_record
        record = get_record(chat_id)
        if record:
            title = str(record.get("title") or "").strip()
            if title:
                return title
    except Exception:
        pass
    return ""


async def handle_remaining(bot, event, chat_id, sender, text, logger=None):
    """📋 دستور «مهلت گروه» — مهلت باقی‌ماندهٔ واقعیِ همان گروه.

    این دستور تاریخ انقضا را تغییر نمی‌دهد؛ فقط رکورد انقضای موجود را
    می‌خواند و مدت باقی‌مانده را از روی تاریخ انقضای واقعی محاسبه می‌کند.
    گروه با ID خودش شناخته می‌شود، پس تغییر نام هرگز گروه جدیدی نمی‌سازد.

    ``True`` یعنی پیام مصرف شد و هندلر اصلی نباید ادامه دهد.
    """
    if match_remaining_command(text) is None:
        return False

    if not _remaining_allowed(chat_id, sender):
        _log(logger, "GROUP REMAINING DENIED "
                     f"chat_id={chat_id} user_id={getattr(sender, 'id', None)}")
        try:
            await event.reply(REMAINING_DENIED)
        except Exception:
            pass
        return True

    # نام «فعلی» گروه: اول از خود چت (با اولین پیام بعد از تغییر نام،
    # اسم جدید گرفته و ذخیره می‌شود)، بعد از ذخیره‌سازی‌های موجود.
    title = getattr(await _safe_chat(event), "title", "") or ""
    title = str(title).strip()
    if title:
        try:
            from modules.group_storage import update_group_title
            update_group_title(chat_id, title)
        except Exception:
            pass
        try:
            update_expiry_title(chat_id, title)
        except Exception:
            pass
    if not title:
        title = _stored_title(chat_id)

    # مهلت باقی‌مانده همیشه از تاریخ انقضای واقعیِ ذخیره‌شده محاسبه
    # می‌شود؛ نه مقدار ثابت، نه کپی قدیمی.
    remaining_text = format_remaining(seconds_left(chat_id))
    text_out, spans = build_remaining_message(title, remaining_text)
    try:
        await event.reply(text_out, formatting_entities=_entities(spans))
    except Exception as error:
        _log_error(logger, f"GROUP REMAINING SEND FAILED "
                           f"chat_id={chat_id} error={error!r}")
        return True
    _log(logger, "GROUP REMAINING SENT "
                 f"chat_id={chat_id} title={title!r} "
                 f"remaining={remaining_text!r} "
                 f"user_id={getattr(sender, 'id', None)}")
    return True


def blocks_message(chat_id, sender):
    """آیا این پیام باید به دلیل انقضای گروه متوقف شود.

    مالک اصلی همیشه عبور می‌کند تا بتواند گروه را دوباره فعال کند.
    """
    if not is_expired(chat_id):
        return False
    return not is_global_owner(sender)


async def run_expiry_watcher(bot, deactivate, interval=None,
                             logger=None, iterations=None):
    """حلقهٔ پس‌زمینه: گروه‌های منقضی را بدون نیاز به هیچ پیامی می‌بندد.

    ``deactivate(chat_id, title)`` توسط فراخوان داده می‌شود تا این ماژول
    به storage گروه‌ها وابسته نشود.
    """
    import asyncio

    delay = CHECK_INTERVAL_SECONDS if interval is None else interval
    rounds = 0
    while True:
        try:
            await check_once(bot, deactivate, logger=logger)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            _log_error(logger, f"GROUP EXPIRY WATCHER FAILED error={error!r}")
        rounds += 1
        if iterations is not None and rounds >= iterations:
            return rounds
        await asyncio.sleep(delay)


async def check_once(bot, deactivate, logger=None):
    """یک بار بررسی می‌کند و هر گروه منقضی را می‌بندد.

    تعداد گروه‌های بسته‌شده را برمی‌گرداند.
    """
    closed = 0
    due = due_groups()
    _log(logger, f"EXPIRY CHECK due_count={len(due)}")
    for key, record in due:
        title = record.get("title", "") or ""
        _log(logger, "EXPIRY FOUND "
                     f"group_id={key} expires_at={record.get('expires_at')} "
                     f"title={title!r}")
        try:
            chat_id = int(key)
        except (TypeError, ValueError):
            chat_id = key

        _log(logger, "EXPIRY ACTION START "
                     f"group_id={chat_id} title={title!r}")
        try:
            deactivate(chat_id, title)
            _log(logger, f"GROUP EXPIRY DEACTIVATED chat_id={chat_id} "
                         f"title={title!r} expires_at={record.get('expires_at')}")
        except Exception as error:
            _log_error(logger, f"GROUP EXPIRY DEACTIVATE FAILED "
                               f"chat_id={chat_id} error={error!r}")
            continue

        message, spans = build_expired_message()
        for target in _targets(chat_id, key):
            try:
                sent = await bot.client.send_message(
                    target, message, formatting_entities=_entities(spans))
                cleanup = getattr(bot, "notice_cleanup", None)
                if cleanup is not None:
                    cleanup.schedule(target, sent)
                if not mark_notified(key):
                    _log_error(logger, "EXPIRY NOTIFICATION STATE FAILED "
                                       f"group_id={key}")
                    continue
                _log(logger, f"EXPIRY NOTIFICATION SENT group_id={key} chat_id={target}")
                _log(logger, f"GROUP EXPIRY NOTICE SENT chat_id={target}")
                break
            except Exception as error:
                _log_error(logger, f"GROUP EXPIRY NOTICE FAILED "
                                   f"chat_id={target} error={error!r}")
                error_text = f"{error!r}".upper()
                if "404" in error_text or "NOT_FOUND" in error_text:
                    mark_notified(key)
                    _log_error(logger, f"EXPIRY TARGET INVALID REMOVED chat_id={target}")
                    break
        closed += 1
    return closed


def _targets(chat_id, key):
    """شکل‌های ممکن شناسه برای ارسال پیام به گروه."""
    targets = []
    try:
        short = int(key)
    except (TypeError, ValueError):
        return [chat_id]
    for candidate in (chat_id, -short, -(1_000_000_000_000 + short), short):
        if candidate not in targets:
            targets.append(candidate)
    return targets
