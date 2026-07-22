from pathlib import Path
import shutil
import datetime

file=Path("handlers/message_handler.py")

backup=Path(
    "handlers/message_handler.before_owner_admin_fix_"
    + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".py"
)

shutil.copy(file, backup)

text=file.read_text(encoding="utf-8")


old1='''sender_username = getattr(sender, "username", None)
              if not is_admin(chat_id, sender_username):
                  await event.reply("❌ فقط ادمین‌ها اجازه استفاده از این دستور را دارند")
                  return

              try:
                  owner = getattr(sender, "username", "")'''


new1='''sender_username = getattr(sender, "username", None)
              if sender_username != "osine1":
                  await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")
                  return

              try:
                  owner = getattr(sender, "username", "")'''


count=text.count(old1)

text=text.replace(old1,new1)

file.write_text(text,encoding="utf-8")

print("تعداد اصلاح:",count)
print("بکاپ:",backup)
print("✅ تمام شد")
