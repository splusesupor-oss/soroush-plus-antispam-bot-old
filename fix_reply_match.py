from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''for key, reply in auto_replies.items():
                if key in clean_text:
                    await event.reply(reply)
                    return'''

new = '''for key, reply in auto_replies.items():
                # پاسخ فقط برای پیام کوتاه و کامل
                if clean_text.strip() == key and len(clean_text) <= 30 and "\\n" not in clean_text:
                    await event.reply(reply)
                    return'''

if old in s:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("✅ پاسخ خودکار اصلاح شد")
else:
    print("❌ کد پیدا نشد")
