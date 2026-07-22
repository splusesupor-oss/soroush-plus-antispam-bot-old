from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = '''# اخطار کاربر با ریپلای
        if clean_text == "اخطار":
            try:
'''

new = '''# اخطار کاربر با ریپلای
        if clean_text == "اخطار":
            try:
                sender = await event.get_sender()
                sender_username = getattr(sender, "username", None)

                if not is_admin(chat_id, sender_username):
                    await event.reply("❌ فقط ادمین‌ها اجازه استفاده از اخطار را دارند")
                    return
'''

if old not in text:
    print("❌ محل اخطار پیدا نشد")
    exit()

text = text.replace(old, new, 1)

p.write_text(text, encoding="utf-8")
print("✅ دسترسی اخطار فقط برای ادمین‌ها فعال شد")
