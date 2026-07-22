from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_admin_self_fix.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

text=text.replace(
    "self.config_manager.is_admin(",
    "bot.config_manager.is_admin("
)

p.write_text(text,encoding="utf-8")

print("✅ self removed")
print("backup:",backup)
