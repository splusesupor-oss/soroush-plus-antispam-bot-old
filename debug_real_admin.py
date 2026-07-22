from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

find = '''if not is_admin(chat_id, sender_username):
                await event.reply("❌ فقط ادمین‌های ثبت شده اجازه استفاده از اخطار را دارند")
                return'''

replace = '''print("DEBUG WARNING ADMIN:", chat_id, sender_username, is_admin(chat_id, sender_username))

            if not is_admin(chat_id, sender_username):
                await event.reply("❌ فقط ادمین‌های ثبت شده اجازه استفاده از اخطار را دارند")
                return'''

if find in text:
    text=text.replace(find, replace, 1)
    p.write_text(text, encoding="utf-8")
    print("✅ دیباگ اضافه شد")
else:
    print("❌ محل پیدا نشد")
