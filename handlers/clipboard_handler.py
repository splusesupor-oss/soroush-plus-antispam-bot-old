"""📮 هندلر مستقل «کپی بورد» (حافظهٔ روباهی).

تنها نقطهٔ اتصال این قابلیت به ربات. هیچ state ای اینجا نگه داشته
نمی‌شود (همه در ``modules/clipboard.py``) و هیچ ماژول بازی/قفل/حافظه‌ای
import نمی‌گردد.

سه مسیر کاملاً جدا:

1. «کپی بورد»  → فقط پیام راهنما را نشان می‌دهد و حالت ذخیره را باز
   می‌کند. هیچ متنی ارسال نمی‌کند.
2. Reply روی همان پیام راهنما → متن کاربر به‌عنوان کپی‌بورد *همان گروه*
   ذخیره می‌شود (با قالب‌بندی اصلی).
3. «کپی» → متن ذخیره‌شده با همان قالب‌بندی ارسال می‌شود.

تطبیق دستورها «دقیق» است، پس هیچ ``startswith`` عمومی‌ای نمی‌تواند
این دو دستور را با چیز دیگری اشتباه بگیرد.
"""
try:
    from splusthon.tl.types import MessageEntityBlockquote, MessageEntityBold
except ImportError:  # محیط تست/CI بدون splusthon
    class MessageEntityBlockquote:
        def __init__(self, offset=0, length=0):
            self.offset = offset
            self.length = length

    class MessageEntityBold:
        def __init__(self, offset=0, length=0):
            self.offset = offset
            self.length = length

from modules import clipboard
from modules.admin_tools import has_admin_permission


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


def _reply_message_id(event):
    """شناسهٔ پیامی که روی آن Reply شده (همهٔ شکل‌های ممکن API)."""
    message = getattr(event, "message", None)
    message_reply = getattr(message, "reply_to", None)
    return (
        getattr(message, "reply_to_msg_id", None)
        or getattr(message_reply, "reply_to_msg_id", None)
        or getattr(event, "reply_to_msg_id", None)
        or getattr(getattr(event, "reply_to", None), "reply_to_msg_id", None)
    )


def _message_text(event, fallback=None):
    """متن خامِ پیام (یا کپشن مدیا)، دست‌نخورده."""
    message = getattr(event, "message", None)
    for value in (getattr(message, "message", None),
                  getattr(message, "text", None),
                  fallback):
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _message_entities(event):
    message = getattr(event, "message", None)
    entities = getattr(message, "entities", None)
    return list(entities) if entities else []


def _allowed(chat_id, sender):
    """دسترسی: فقط مالک ثبت‌شده و ادمین‌های ربات/گروه.

    عمداً از همان ``admin_tools.has_admin_permission`` پروژه استفاده
    می‌شود (مالک اصلی ربات، مالک گروه، ادمین ثبت‌شده) و سیستم تشخیص
    ادمین جدیدی ساخته نمی‌شود.
    """
    try:
        return bool(has_admin_permission(
            chat_id,
            getattr(sender, "id", sender),
            (getattr(sender, "username", None) or "").lstrip("@"),
        ))
    except Exception:
        return False


async def _reply(event, text, entities=None):
    return await event.reply(text, formatting_entities=entities or None)


async def handle(bot, event, chat_id, user_id, sender, text,
                 raw_text=None, logger=None):
    """``True`` یعنی پیام مصرف شد و هندلر اصلی نباید ادامه دهد."""
    mode = clipboard.match_command(text)
    reply_id = _reply_message_id(event)

    # -------------------------------------------------------------- دستورها
    if mode is not None:
        if not _allowed(chat_id, sender):
            _log(logger, "CLIPBOARD DENIED "
                         f"chat_id={chat_id} user_id={user_id} mode={mode}")
            if mode == clipboard.MODE_SHOW:
                # «کپی» یک واژهٔ روزمرهٔ فارسی هم هست. برای کاربر عادی
                # پیام خطا فرستاده نمی‌شود تا گروه پر از هشدار نشود؛
                # پیام مثل یک چت معمولی به مسیر عادی ادامه می‌دهد.
                return False
            try:
                await _reply(event, clipboard.DENIED_MESSAGE)
            except Exception as error:
                _log_error(logger, f"CLIPBOARD DENY REPLY FAILED: {error!r}")
            return True

        if mode == clipboard.MODE_SAVE:
            return await _send_help(event, chat_id, user_id, logger)
        return await _send_clipboard(event, chat_id, user_id, logger)

    # ------------------------------------------- ذخیره فقط با Reply به راهنما
    if reply_id is None or not clipboard.is_help_message(chat_id, reply_id):
        return False

    if not _allowed(chat_id, sender):
        # پیام یک کاربر عادی مصرف نمی‌شود: مسیر عادی ربات باید
        # دست‌نخورده ادامه پیدا کند.
        _log(logger, "CLIPBOARD SAVE DENIED "
                     f"chat_id={chat_id} user_id={user_id} reason=not_admin")
        return False

    return await _store(event, chat_id, user_id, raw_text, logger)


async def _send_help(event, chat_id, user_id, logger):
    help_text, spans = clipboard.build_help_message()
    try:
        sent = await _reply(event, help_text, _entities(spans))
    except Exception as error:
        _log_error(logger, "CLIPBOARD HELP SEND FAILED "
                           f"chat_id={chat_id} error={error!r}")
        return True
    message_id = getattr(sent, "id", None)
    if message_id is None:
        _log_error(logger, "CLIPBOARD HELP NO MESSAGE ID "
                           f"chat_id={chat_id}")
        return True
    clipboard.open_save_mode(chat_id, message_id)
    _log(logger, "CLIPBOARD HELP SENT "
                 f"chat_id={chat_id} user_id={user_id} "
                 f"help_message_id={message_id}")
    return True


async def _send_clipboard(event, chat_id, user_id, logger):
    text, entities = clipboard.get(chat_id)
    if text is None:
        _log(logger, f"CLIPBOARD SHOW EMPTY chat_id={chat_id}")
        try:
            await _reply(event, clipboard.EMPTY_MESSAGE)
        except Exception as error:
            _log_error(logger, f"CLIPBOARD EMPTY REPLY FAILED: {error!r}")
        return True
    try:
        await _reply(event, text, entities)
    except Exception as error:
        # قالب‌بندی ذخیره‌شده ممکن است با نسخهٔ فعلی API سازگار نباشد؛
        # متن نباید قربانی شود، پس بدون entity دوباره تلاش می‌شود.
        _log_error(logger, "CLIPBOARD SHOW FAILED "
                           f"chat_id={chat_id} error={error!r}")
        try:
            await _reply(event, text)
        except Exception as second:
            _log_error(logger, "CLIPBOARD SHOW PLAIN FAILED "
                               f"chat_id={chat_id} error={second!r}")
            return True
    _log(logger, "CLIPBOARD SHOWN "
                 f"chat_id={chat_id} user_id={user_id} chars={len(text)} "
                 f"entities={len(entities)}")
    return True


async def _store(event, chat_id, user_id, raw_text, logger):
    body = _message_text(event, raw_text)
    ok, problem = clipboard.validate(body)
    if not ok:
        _log(logger, "CLIPBOARD SAVE REJECTED "
                     f"chat_id={chat_id} user_id={user_id} "
                     f"reason={problem!r}")
        try:
            await _reply(event, problem)
        except Exception as error:
            _log_error(logger, f"CLIPBOARD REJECT REPLY FAILED: {error!r}")
        return True

    entities = _message_entities(event)
    try:
        clipboard.save(chat_id, body, entities, user_id=user_id)
    except Exception as error:
        _log_error(logger, "CLIPBOARD SAVE FAILED "
                           f"chat_id={chat_id} error={error!r}")
        return True
    _log(logger, "CLIPBOARD SAVED "
                 f"chat_id={chat_id} user_id={user_id} chars={len(body)} "
                 f"entities={len(entities)}")
    try:
        await _reply(event, clipboard.SAVED_MESSAGE)
    except Exception as error:
        _log_error(logger, f"CLIPBOARD SAVED REPLY FAILED: {error!r}")
    return True
