from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''"🎯 بازی جرعت حقیقت:",
                      "✍️ ساخت فونت:",'''

new = '''"🎯 بازی جرعت حقیقت:",
                      "🧩 چیستان:",
                      "🚫 خاموش کردن فیلتر کلمات:",
                      "✅ روشن کردن فیلتر کلمات:",
                      "✍️ ساخت فونت:",'''

if old in s:
    s = s.replace(old, new, 1)
    print("✅ عنوان‌ها برای بولد اضافه شدند")
else:
    print("❌ لیست پیدا نشد")

p.write_text(s, encoding="utf-8")
