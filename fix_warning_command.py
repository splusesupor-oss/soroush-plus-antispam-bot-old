from pathlib import Path
import shutil
from datetime import datetime

FILE = Path("handlers/message_handler.py")

backup = FILE.with_suffix(
    ".py.bak_warning_" + datetime.now().strftime("%Y%m%d_%H%M%S")
)

shutil.copy(FILE, backup)

text = FILE.read_text(encoding="utf-8")

marker = '# سکوت کاربر با ریپلای'

if 'if clean_text == "اخطار":' in text:
    print("⚠️ دستور اخطار قبلا وجود دارد")
    exit()

patch = r'''
# اخطار کاربر با ریپلای
if clean_text == "اخطار":
    try:
        sender = await event.get_sender()
        sender_username = getattr(sender, "username", None)

        if not is_admin(chat_id, sender_username):
            await event.reply("❌ فقط ادمین‌ها اجازه اخطار دارند")
            return

        if not event.reply_to:
            await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
            return

        reply_msg = await bot.client.get_messages(
            chat_id,
            ids=event.reply_to.reply_to_msg_id
        )

        if not reply_msg:
            await event.reply("❌ پیام پیدا نشد")
            return

        target_user = await reply_msg.get_sender()

        if not target_user:
            await event.reply("❌ کاربر پیدا نشد")
            return

        username = getattr(target_user, "username", None) or "کاربر"

        await event.reply(
            f"⚠️ اخطار برای {username} ثبت شد"
        )

    except Exception as e:
        bot.logger.log_error(f"خطای اخطار: {e}")
        await event.reply(f"❌ خطا در اخطار:\n{e}")

    return

'''

if marker not in text:
    print("❌ محل قرار دادن پیدا نشد")
    exit()

text = text.replace(marker, patch + marker, 1)

FILE.write_text(text, encoding="utf-8")

print("✅ دستور اخطار اضافه شد")
print("BACKUP:", backup)
