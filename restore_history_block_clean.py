from pathlib import Path
import shutil

bad = Path("handlers/message_handler.py")
backup = Path("handlers/message_handler.before_force_history_delete")

if not backup.exists():
    print("❌ backup not found")
    exit()

shutil.copy(backup, bad)

print("✅ restored before force fix")

