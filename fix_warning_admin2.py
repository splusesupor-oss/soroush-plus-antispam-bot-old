from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

target = 'if clean_text == "اخطار":'

pos = text.find(target)

if pos == -1:
    print("❌ اخطار پیدا نشد")
    exit()

insert_pos = pos + len(target)

add = '''

            sender = await event.get_sender()
            sender_username = getattr(sender, "username", None)

            if not is_admin(chat_id, sender_username):
                await event.reply("❌ فقط ادمین‌ها اجازه استفاده از اخطار را دارند")
                return
'''

# جلوگیری از دوبار اضافه شدن
if "فقط ادمین‌ها اجازه استفاده از اخطار را دارند" in text[pos:pos+500]:
    print("⚠️ قبلا اضافه شده")
else:
    text = text[:insert_pos] + add + text[insert_pos:]
    p.write_text(text, encoding="utf-8")
    print("✅ محدودیت اخطار اضافه شد")

