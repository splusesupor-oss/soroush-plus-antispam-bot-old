from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.py.before_clear_import2")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

text=text.replace(
"get_message_ids, clear_user",
"get_message_ids"
)

p.write_text(text,encoding="utf-8")

print("✅ import fixed")
print("backup:",backup)
