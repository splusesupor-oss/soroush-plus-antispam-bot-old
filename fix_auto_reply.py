from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''if clean_text in auto_replies:
                await event.reply(auto_replies[clean_text])
                return'''

new = '''# پاسخ خودکار فقط برای پیام کوتاه و سالم
            if (
                clean_text in auto_replies
                and len(clean_text) <= 30
                and "\\n" not in clean_text
            ):
                await event.reply(auto_replies[clean_text])
                return'''

if old in s:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("✅ پاسخ خودکار محدود شد")
else:
    print("❌ بخش موردنظر پیدا نشد")
