from pathlib import Path
import re

f=Path("handlers/message_handler.py")

text=f.read_text(encoding="utf-8")

commands=[
"ثبت ادمین",
"برکناری ادمین",
"اخطار",
"سکوت",
"رفع سکوت",
"اخراج",
"پاک",
]

print("🔍 بررسی محافظ دستورات ادمین\n")

for cmd in commands:
    pos=text.find(cmd)

    if pos==-1:
        print("❌ پیدا نشد:",cmd)
        continue

    start=max(0,pos-500)
    block=text[start:pos+500]

    if "is_admin" in block:
        print("✅ محافظ دارد:",cmd)
    else:
        print("❌ بدون محافظ:",cmd)


print("\n🔍 تعداد استفاده از is_admin:")
print(text.count("is_admin"))

print("\n🔍 import:")
for line in text.splitlines():
    if "admin_storage" in line:
        print(line)
