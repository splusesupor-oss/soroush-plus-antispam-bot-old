from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_remove_bad_is_admin.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

text=text.replace("from modules.admin_actions import is_admin\n","")

p.write_text(text,encoding="utf-8")

print("✅ bad import removed")
print("backup:",backup)
