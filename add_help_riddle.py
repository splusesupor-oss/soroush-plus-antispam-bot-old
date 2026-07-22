from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_help_riddle_add"

shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

old = '''                      "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n\\n"
'''

new = '''                      "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n\\n"
                      "**🧩 چیستان**\\n"
                      "یک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن\\n\\n"
'''

if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ چیستان به راهنما اضافه شد")
    print("📦 بکاپ:", backup)
else:
    print("❌ محل پیدا نشد")
