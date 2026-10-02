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



_PROBE_FIELDS = (
    "first_name", "last_name", "username", "title", "name",
    "deleted", "bot", "fake", "scam", "id",
)


def _describe(obj):
    """خلاصهٔ فیلدهای نام‌دارِ یک آبجکت، برای فهمیدن شکل واقعی داده."""
    if obj is None:
        return "None"
    parts = [type(obj).__name__]
    for field in _PROBE_FIELDS:
        try:
            value = getattr(obj, field, None)
        except Exception as error:
            value = f"<err {error!r}>"
        if value in (None, "", False):
            continue
        text = str(value)
        if len(text) > 40:
            text = text[:40] + "…"
        parts.append(f"{field}={text}")
    return " | ".join(parts)


async def _dump_sources(bot, event, sender):
    """هر منبعی که ممکن است نام واقعی کاربر را داشته باشد را می‌آزماید."""
    lines = []
    client = getattr(bot, "client", None)
    replied = None
    try:
        replied = await event.get_reply_message()
    except Exception as error:
        lines.append(f"get_reply_message → خطا {error!r}")

    target_id = None
    handle = None

    if replied is not None:
        for field in ("sender_id", "post_author", "from_id"):
            try:
                value = getattr(replied, field, None)
            except Exception:
                value = None
            if value not in (None, ""):
                lines.append(f"message.{field} = {str(value)[:50]}")
        cached = getattr(replied, "sender", None)
        lines.append(f"message.sender → {_describe(cached)}")
        if cached is None:
            try:
                cached = await replied.get_sender()
                lines.append(f"get_sender() → {_describe(cached)}")
            except Exception as error:
                lines.append(f"get_sender() → خطا {error!r}")
        target_id = getattr(cached, "id", None) or getattr(
            replied, "sender_id", None)
        handle = (getattr(cached, "username", None) or "").lstrip("@")
    else:
        lines.append(f"فرستندهٔ دستور → {_describe(sender)}")
        target_id = getattr(sender, "id", None)
        handle = (getattr(sender, "username", None) or "").lstrip("@")

    if client is not None and target_id:
        try:
            lines.append(
                f"get_entity(id) → {_describe(await client.get_entity(target_id))}")
        except Exception as error:
            lines.append(f"get_entity(id) → خطا {error!r}")
    if client is not None and handle:
        try:
            lines.append(
                f"get_entity(@) → {_describe(await client.get_entity(handle))}")
        except Exception as error:
            lines.append(f"get_entity(@) → خطا {error!r}")

    if client is not None and target_id:
        try:
            from splusthon.tl.functions.users import GetFullUserRequest

            full = await client(GetFullUserRequest(target_id))
            users = getattr(full, "users", None)
            if users:
                lines.append(f"GetFullUser.users[0] → {_describe(users[0])}")
            else:
                inner = getattr(full, "user", None) or getattr(
                    full, "full_user", None)
                lines.append(f"GetFullUser → {_describe(inner)}")
        except Exception as error:
            lines.append(f"GetFullUser → خطا {error!r}")

    if client is not None and target_id:
        try:
            from splusthon.tl.functions.channels import GetParticipantRequest

            part = await client(GetParticipantRequest(
                getattr(event, "chat_id", None), target_id))
            users = getattr(part, "users", None)
            if users:
                lines.append(f"GetParticipant.users[0] → {_describe(users[0])}")
        except Exception as error:
            lines.append(f"GetParticipant → خطا {error!r}")

    return lines

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

    if action == name_filters.ACTION_DEBUG:
        lines = ["🧪 دیباگ خواندن نام نمایشی", ""]
        try:
            lines.extend(await _dump_sources(bot, event, sender))
        except Exception as error:
            lines.append(f"دامپ شکست خورد: {error!r}")
        body = "\n".join(lines)
        _log(logger, "NAME FILTER DEBUG "
                     f"chat_id={chat_id} user_id={user_id} "
                     f"lines={len(lines)}")
        _log(logger, "NAME FILTER DEBUG BODY " + body.replace("\n", " ~ "))
        await _safe_reply(event, body[:3500],
                          [("bold", 0, name_filters.u16_len(lines[0]))],
                          logger)
        return True

    if action == name_filters.ACTION_TEST:
        # هدف: کاربرِ پیامِ ریپلای‌شده، وگرنه متنِ بعد از دستور،
        # وگرنه خودِ فرستنده.
        target = None
        try:
            replied = await event.get_reply_message()
            if replied is not None:
                target = getattr(replied, "sender", None)
                if target is None:
                    target = await replied.get_sender()
        except Exception as error:
            _log_error(logger, f"NAME FILTER TEST REPLY FAILED: {error!r}")
        raw = term or None
        if target is None and not raw:
            target = sender
        # اگر پروفایل ناقص آمده بود، یک بار دوباره entity را می‌گیریم تا
        # گزارش، همان چیزی را نشان دهد که enforcement می‌بیند.
        if target is not None and name_filters.is_unresolved(
            name_filters.display_name(target)
        ):
            client = getattr(bot, "client", None)
            probes = [getattr(target, "id", None),
                      (getattr(target, "username", None) or "").lstrip("@")]
            for probe in probes:
                if not probe or client is None:
                    continue
                try:
                    fresh = await client.get_entity(probe)
                except Exception:
                    continue
                if fresh is not None and not name_filters.is_unresolved(
                    name_filters.display_name(fresh)
                ):
                    _log(logger, "NAME FILTER TEST RESOLVED "
                                 f"probe={probe!r} "
                                 f"name={name_filters.display_name(fresh)!r}")
                    target = fresh
                    break
        body, spans = name_filters.build_test_message(chat_id, target, raw)
        _log(logger, "NAME FILTER TEST "
                     f"chat_id={chat_id} "
                     f"storage_key={normalize_group_id(chat_id)!r} "
                     f"user_id={user_id} "
                     f"target={name_filters.display_name(target)!r} "
                     f"raw={raw!r} "
                     f"terms={name_filters.list_terms(chat_id)!r}")
        await _safe_reply(event, body, spans, logger)
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
