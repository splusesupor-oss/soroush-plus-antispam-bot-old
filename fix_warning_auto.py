from pathlib import Path
import shutil
from datetime import datetime

FILE = Path("handlers/message_handler.py")

backup = FILE.with_name(
    FILE.name + ".bak_warning_auto_" + datetime.now().strftime("%Y%m%d_%H%M%S")
)

shutil.copy(FILE, backup)

text = FILE.read_text(encoding="utf-8")

marker = "# سکوت کاربر با ریپلای"

if "if clean_text == \"اخطار\":" in text:
    print("⚠️ دستور اخطار قبلا وجود دارد")
    print("BACKUP:", backup)
    exit()

insert = '''
# اخطار کاربر با ریپلای
        if clean_text == "اخطار":
            try:
                if not event.reply_to:
                    await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
                    return

                reply_msg = await bot.client.get_messages(
                    chat_id,
                    ids=event.reply_to.reply_to_msg_id
                )

                user = await reply_msg.get_sender()

                if not user:
                    await event.reply("❌ کاربر پیدا نشد")
                    return

                username = getattr(user, "username", None) or "کاربر"

                await event.reply(f"⚠️ اخطار برای {username} ثبت شد")

            except Exception as e:
                await event.reply(f"❌ خطا در اخطار:\\n{e}")

            return

'''

if marker not in text:
    print("❌ محل قرار دادن پیدا نشد")
    print("BACKUP:", backup)
    exit()

text = text.replace(marker, insert + marker, 1)

FILE.write_text(text, encoding="utf-8")

print("✅ دستور اخطار خودکار اضافه شد")
print("BACKUP:", backup)
