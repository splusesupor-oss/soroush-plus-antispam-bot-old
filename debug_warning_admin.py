from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = '''if not is_admin(chat_id, sender_username):
                                await event.reply("❌ فقط ادمین‌ها اجازه استفاده از اخطار را دارند")
                                return'''

new = '''print("DEBUG WARNING ADMIN:", chat_id, sender_username, is_admin(chat_id, sender_username))

                            if not is_admin(chat_id, sender_username):
                                await event.reply("❌ فقط ادمین‌ها اجازه استفاده از اخطار را دارند")
                                return'''

if old not in text:
    print("❌ محل پیدا نشد")
else:
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")
    print("✅ دیباگ اضافه شد")
