from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

target = '    # اطلاعات پیام\n'

insert = '''
    # بررسی اسپم رسانه‌ای (عکس و فایل)
    try:
        if check_media_spam(event.message):
            await add_delete(event.chat_id, event.message.id)
            return
    except Exception as e:
        print("media check error:", e)

'''

if "بررسی اسپم رسانه‌ای" not in text:
    text = text.replace(target, target + insert)

p.write_text(text, encoding="utf-8")

print("✅ media check connected")
