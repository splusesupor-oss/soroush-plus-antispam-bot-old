from pathlib import Path
import re

p = Path("main.py")
s = p.read_text(encoding="utf-8")

pattern = r'("🎯 بازی جرعت حقیقت:\\n".*?)(\s+"✍️ ساخت فونت:\\n")'

replacement = r'''\1
                      "**🧩 چیستان:**\\n"
                      "یک معمای تصادفی دریافت کنید 🧩\\n"
                      "۵۰ ثانیه فرصت دارید\\n\\n"
\2'''

s2, count = re.subn(pattern, replacement, s, count=1, flags=re.S)

if count:
    print("✅ چیستان درست شد")
else:
    print("❌ بخش بازی پیدا نشد")

p.write_text(s2, encoding="utf-8")
