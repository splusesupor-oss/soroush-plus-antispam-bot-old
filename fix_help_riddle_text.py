from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_help_riddle_text"

shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

old = "جرعت حقیقت\n🧩 چیستان"

new = "جرعت حقیقت\n\n**🧩 چیستان**\nیک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن"

if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ متن چیستان در راهنما اصلاح شد")
    print("📦 بکاپ:", backup)
else:
    print("❌ بخش قبلی پیدا نشد")

