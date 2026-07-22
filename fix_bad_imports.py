from pathlib import Path
import re

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

# حذف import اشتباه
t=re.sub(
r'from fix_banned_storage_regex import remove_banned\n',
'',
t
)

# اگر وجود ندارد از فایل اصلی اضافه کن
if "from modules.banned_storage import remove_banned" not in t:
    t="from modules.banned_storage import remove_banned\n"+t

p.write_text(t,encoding="utf-8")

print("✅ BAD IMPORT FIXED")
