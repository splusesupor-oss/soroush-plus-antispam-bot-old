"""📥 هندلرِ قابلیت «دانلود عکس» — نقطهٔ اتصالِ مستقل به ربات.

``handle`` مقدار True برمی‌گرداند یعنی پیام مصرف شد و هندلر اصلی نباید
ادامه دهد.

جریان:
  «دانلود عکس» → درخواستِ عبارت → تأیید → (فیلتر + جستجو + دانلود + ارسال +
  کسرِ ۲۰ برنز) — همه با قفلِ گروه و صفِ کاربر.
"""
import asyncio

from modules import photo_download
from modules.photo_download import (
    COMMAND,
    ASK_QUERY,
    BUSY_GROUP,
    BUSY_USER,
)


def _log(bot, message):
    try:
        bot.logger.log_info(message)
    except Exception:
        pass


async def handle(bot, event, chat_id, user_id, sender, text, logger=None):
    """پیامِ مربوط به دانلود عکس را پردازش می‌کند. True یعنی مصرف شد."""
    clean = (text or "").strip()

    # ۱) دستورِ شروع — دو حالت:
    #    «دانلود عکس»              → بعداً عبارت می‌خواهیم
    #    «دانلود عکس گربه»         → عبارت همان‌جا آمده
    if clean == COMMAND or clean.startswith(COMMAND + " "):
        if photo_download.is_busy(chat_id, user_id):
            if chat_id in photo_download._BUSY_GROUPS:
                await event.reply(BUSY_GROUP)
            else:
                await event.reply(BUSY_USER)
            return True
        photo_download.start_session(chat_id, user_id)
        # استخراج عبارتِ همراهِ دستور (اگر باشد)
        inline_query = clean[len(COMMAND):].strip() if len(clean) > len(COMMAND) else ""
        if inline_query:
            # عبارتِ همراه → فیلتر/موجودی → پیامِ تأیید (بدون پرسیدنِ دوباره)
            result, payload = photo_download.handle_query(
                chat_id, user_id, inline_query)
            if result == "blocked":
                await event.reply(payload)
                _log(bot, f"PHOTO DOWNLOAD BLOCKED chat_id={chat_id} "
                          f"user_id={user_id} query={inline_query!r}")
                return True
            if result == "insufficient":
                await event.reply(payload)
                return True
            if result == "ask_confirm":
                await event.reply(payload)
                return True
        else:
            await event.reply(ASK_QUERY)
        _log(bot, f"PHOTO DOWNLOAD START chat_id={chat_id} user_id={user_id} "
                  f"inline_query={inline_query!r}")
        return True

    # ۲) اگر کاربر جریانِ فعال دارد، پیامِ او همان مرحلهٔ جریان است
    s = photo_download.session(chat_id, user_id)
    if s is None:
        return False

    # ۲-الف) اگر هنوز عبارت داده نشده
    if s.get("query") is None:
        result, payload = photo_download.handle_query(chat_id, user_id, clean)
        if result == "no_session":
            return False
        if result == "blocked":
            await event.reply(payload)
            _log(bot, f"PHOTO DOWNLOAD BLOCKED chat_id={chat_id} user_id={user_id} query={clean!r}")
            return True
        if result == "insufficient":
            await event.reply(payload)
            return True
        if result == "ask_confirm":
            await event.reply(payload)
            return True
        return True

    # ۲-ب) عبارت داده شده → بررسیِ تأیید/لغو
    result, payload = photo_download.handle_confirm(chat_id, user_id, clean)
    if result == "cancel":
        await event.reply(payload)
        return True
    if result == "invalid":
        await event.reply(payload)
        return True
    if result == "no_session":
        return False
    if result == "start":
        # تأیید شد: اجرای کامل، بدون بلاک کردن Event Loop
        await event.reply("🔄 در حال جستجو و ارسال تصاویر...")
        outcome, message = await photo_download.process(chat_id, user_id, bot)
        if outcome in {"done", "no_results", "error"}:
            await event.reply(message)
            _log(bot, f"PHOTO DOWNLOAD {outcome.upper()} chat_id={chat_id} user_id={user_id}")
        return True

    return False
