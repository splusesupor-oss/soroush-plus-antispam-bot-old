from pathlib import Path
import shutil
import datetime
import re

file=Path("handlers/message_handler.py")

backup=file.with_name(
    "message_handler.before_auto_admin_guard_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(file,backup)

text=file.read_text(encoding="utf-8")


targets=[
    "اخطار",
    "سکوت",
    "رفع سکوت",
    "اخراج"
]


for cmd in targets:
    pos=text.find(f'if clean_text == "{cmd}"')
    if pos==-1:
        pos=text.find(f'if clean_text.startswith("{cmd}")')

    if pos==-1:
        print("❌ پیدا نشد:",cmd)
        continue

    block=text[pos:pos+500]

    if "is_admin(" in block or "is_admin_user" in block:
        print("✅ محافظ دارد:",cmd)
    else:
        print("❌ بدون محافظ:",cmd,"در محل",text[:pos].count("\n")+1)


print("\n📌 بکاپ:",backup)

