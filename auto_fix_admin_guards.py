from pathlib import Path
import shutil
import datetime
import re

file=Path("handlers/message_handler.py")

backup=file.with_name(
    "message_handler.before_admin_guard_fix_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(file,backup)

text=file.read_text(encoding="utf-8")


commands=[
("ثبت ادمین","ثبت ادمین"),
("برکناری ادمین","برکناری ادمین"),
("اخطار","اخطار"),
("سکوت","سکوت"),
("رفع سکوت","رفع سکوت"),
("اخراج","اخراج"),
]


for name,cmd in commands:

    pattern=f'if clean_text.startswith("{cmd}")'

    if pattern in text:
        print("⏭ موجود:",cmd)
        continue


print("🔎 بررسی ساختار انجام شد")
print("📌 بکاپ:",backup)

file.write_text(text,encoding="utf-8")

