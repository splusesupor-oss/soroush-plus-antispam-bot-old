from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_admin_call_fix.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

text=text.replace(
    "is_admin(",
    "self.config_manager.is_admin("
)

p.write_text(text,encoding="utf-8")

print("✅ admin call fixed")
print("backup:",backup)
