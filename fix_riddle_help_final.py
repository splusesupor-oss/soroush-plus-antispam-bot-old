from pathlib import Path
import re

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = re.compile(
r'"🎯 بازی جرعت حقیقت:\\n".*?'
r'"✍️ ساخت فونت:\\n"',
re.S
)

new = '''"🎯 بازی جرعت حقیقت:\\n"
                      "جرعت → یک جرعت تصادفی دریافت کنید\\n"
                      "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n\\n"
                      "**🧩 چیستان:**\\n"
                      "یک معمای تصادفی دریافت کنید 🧩\\n"
                      "۵۰ ثانیه فرصت دارید\\n\\n"

                      "✍️ ساخت فونت:\\n"'''

s2, n = old.subn(new, s, count=1)

if n:
    print("✅ بخش چیستان اصلاح شد")
else:
    print("❌ بخش پیدا نشد")

p.write_text(s2, encoding="utf-8")
