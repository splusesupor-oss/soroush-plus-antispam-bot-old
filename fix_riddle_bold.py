from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_riddle_bold_final"

shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

old = '''for word in [
                        "💬 پاسخ‌های ساده:",
'''

new = '''for word in [
                        "🧩 چیستان",
                        "💬 پاسخ‌های ساده:",
'''

if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ چیستان به بولدها اضافه شد")
    print("📦 بکاپ:", backup)
else:
    print("❌ محل پیدا نشد")
