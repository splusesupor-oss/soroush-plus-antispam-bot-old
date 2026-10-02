"""🚫 هندلر مستقل «فیلتر اسم».

تنها نقطهٔ اتصال دستورهای فیلتر اسم به ربات:

* ``فیلتر اسم <عبارت>``      → افزودن عبارت به فیلتر نامِ همان گروه
* ``لغو اسم <عبارت>``        → حذف همان یک عبارت
* ``حذف فیلتر اسم <عبارت>``  → مترادف «لغو اسم»
* ``لیست فیلتر اسم``         → نمایش فیلترهای همان گروه

این سیستم کاملاً مستقل است: ذخیره‌سازی، نرمال‌سازی و تطبیق ایموجی
همگی در ``modules/name_filters`` پیاده شده‌اند و هیچ وابستگی‌ای به
سامانهٔ «نام تبلیغاتی» ندارند. گیت تشخیص در ابتدای
``handlers/message_handler`` است و فقط *اجرای مجازات* (حذف پیام و
سکوت/اخراج طبق تنظیم فعلی گروه) از enforcement موجود ربات می‌آید.
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

from modules import name_filters
from modules.admin_tools import has_admin_permission
from modules.group_id import normalize_group_id


def _entities(spans):
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


def _allowed(chat_id, sender):
    """فقط مالک ثبت‌شده و ادمین ثبت‌شده.

    عمداً از همان ``admin_tools.has_admin_permission`` موجود استفاده
    می‌شود (مالک اصلی ربات، مالک ثبت‌شدهٔ گروه، ادمین ثبت‌شدهٔ گروه)؛
    سیستم تشخیص ادمین جدیدی ساخته نشده است.
    """
    try:
        return bool(has_admin_permission(
            chat_id,
            getattr(sender, "id", sender),
            (getattr(sender, "username", None) or "").lstrip("@"),
        ))
    except Exception:
        return False


async def _reply(event, text, spans=None):
    return await event.reply(
        text, formatting_entities=_entities(spans) if spans else None)


async def handle(bot, event, chat_id, user_id, sender, text, logger=None):
    """``True`` یعنی پیام مصرف شد و هندلر اصلی نباید ادامه دهد."""
    matched = name_filters.match_command(text)
    if matched is None:
        return False
    action, term = matched

    if not _allowed(chat_id, sender):
        _log(logger, "NAME FILTER DENIED "
                     f"chat_id={chat_id} user_id={user_id} action={action}")
        try:
            await _reply(event, name_filters.DENIED_MESSAGE)
        except Exception as error:
            _log_error(logger, f"NAME FILTER DENY REPLY FAILED: {error!r}")
        return True

    if action == name_filters.ACTION_LIST:
        body, spans = name_filters.build_list_message(chat_id)
        await _safe_reply(event, body, spans, logger)
        _log(logger, "NAME FILTER LIST "
                     f"chat_id={chat_id} "
                     f"storage_key={normalize_group_id(chat_id)!r} "
                     f"user_id={user_id} "
                     f"terms={name_filters.list_terms(chat_id)!r} "
                     f"file={name_filters.FILE}")
        return True

    if action == name_filters.ACTION_ADD:
        ok, problem, display = name_filters.add(chat_id, term, user_id=user_id)
        if not ok:
            _log(logger, "NAME FILTER ADD REJECTED "
                         f"chat_id={chat_id} user_id={user_id} "
                         f"term={term!r} reason={problem!r}")
            await _safe_reply(event, problem, None, logger)
            return True
        body, spans = name_filters.build_added_message(display)
        _log(logger, "NAME FILTER ADDED "
                     f"chat_id={chat_id} "
                     f"storage_key={normalize_group_id(chat_id)!r} "
                     f"user_id={user_id} term={display!r} "
                     f"now={name_filters.list_terms(chat_id)!r} "
                     f"file={name_filters.FILE}")
        await _safe_reply(event, body, spans, logger)
        return True

    ok, problem, display = name_filters.remove(chat_id, term)
    if not ok:
        _log(logger, "NAME FILTER REMOVE REJECTED "
                     f"chat_id={chat_id} user_id={user_id} "
                     f"term={term!r} reason={problem!r}")
        await _safe_reply(event, problem, None, logger)
        return True
    body, spans = name_filters.build_removed_message(display)
    _log(logger, "NAME FILTER REMOVED "
                 f"chat_id={chat_id} "
                 f"storage_key={normalize_group_id(chat_id)!r} "
                 f"user_id={user_id} term={display!r} "
                 f"now={name_filters.list_terms(chat_id)!r}")
    await _safe_reply(event, body, spans, logger)
    return True


async def _safe_reply(event, text, spans, logger):
    try:
        await _reply(event, text, spans)
    except Exception as error:
        _log_error(logger, f"NAME FILTER REPLY FAILED: {error!r}")
        try:
            await event.reply(text)
        except Exception as second:
            _log_error(logger,
                       f"NAME FILTER PLAIN REPLY FAILED: {second!r}")
