from pathlib import Path
import shutil,datetime

p=Path("handlers/message_handler.py")

backup=Path(
"handlers/message_handler.before_remove_telethon_import_"+
datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

text=text.replace(
"from telethon import functions\n",
""
)

p.write_text(text,encoding="utf-8")

print("✅ import telethon حذف شد")
print("📌 بکاپ:",backup)
