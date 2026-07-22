#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("modules/riddles.py")

if not p.exists():
    print("❌ modules/riddles.py پیدا نشد")
    exit()

s = p.read_text(encoding="utf-8")

# تغییر زمان‌ها
s = s.replace("120", "50")
s = s.replace("2 * 60", "50")
s = s.replace("120 ثانیه", "50 ثانیه")
s = s.replace("۲ دقیقه", "۵۰ ثانیه")
s = s.replace("دو دقیقه", "۵۰ ثانیه")

# اگر پیام شمارش زمان دارد
s = s.replace("زمان پاسخ: 50", "زمان پاسخ: ۵۰")
s = s.replace("50 ثانیه فرصت", "۵۰ ثانیه فرصت")

p.write_text(s, encoding="utf-8")

print("✅ زمان چیستان شد ۵۰ ثانیه")
PY

python3 -m py_compile modules/riddles.py && echo "✅ syntax ok"

