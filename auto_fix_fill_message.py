from pathlib import Path
import shutil, datetime

p = Path("handlers/message_handler.py")

backup = p.with_name(
    p.stem + ".before_fill_message_" +
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + p.suffix
)

shutil.copy2(p, backup)

text = p.read_text(encoding="utf-8", errors="ignore")

old = 'await event.reply("✅ جواب درست بود!\\n⭐ امتیاز گرفتی")'
new = 'await event.reply("🎉 آفرین! درست بود\\n⭐ امتیاز گرفتی")'

if old in text:
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")
    print("✅ فقط پیام جواب درست جای خالی تغییر کرد")
else:
    print("⚠️ پیام پیدا نشد، تغییری انجام نشد")

print("📌 بکاپ:", backup)
