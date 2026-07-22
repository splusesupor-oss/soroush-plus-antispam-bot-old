from pathlib import Path
import shutil,datetime,re

p=Path("handlers/message_handler.py")

backup=p.with_name(
    "message_handler.before_remove_banned_anywhere_"+
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

old=text

# حذف هر خطی که remove_banned را صدا می‌زند
text=re.sub(
    r'^\s*remove_banned\(chat_id,\s*username\)\s*$',
    '',
    text,
    flags=re.MULTILINE
)

# حذف بلاک if username فقط اگر خالی مانده باشد
text=re.sub(
    r'^\s*username\s*=\s*getattr\(user,\s*"username",\s*None\)\s*\n\s*if username:\s*\n\s*$',
    '',
    text,
    flags=re.MULTILINE
)

if text != old:
    p.write_text(text,encoding="utf-8")
    print("✅ remove_banned حذف شد")
else:
    print("⚠️ چیزی برای حذف پیدا نشد")

print("📌 بکاپ:",backup)
