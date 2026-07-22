from pathlib import Path
import shutil,datetime

p=Path("handlers/message_handler.py")

backup=p.with_name(
    "message_handler.before_remove_banned_cleanup_"+
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

old='''                  username = getattr(user, "username", None)

                  if username:
                      remove_banned(chat_id, username)
'''

if old in text:
    text=text.replace(old,"")
    p.write_text(text,encoding="utf-8")
    print("✅ remove_banned قدیمی حذف شد")
else:
    print("⚠️ بخش قدیمی پیدا نشد")

print("📌 بکاپ:",backup)
