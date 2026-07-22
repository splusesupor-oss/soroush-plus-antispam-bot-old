from pathlib import Path
import shutil

target = Path("handlers/message_handler.py")

sources = [
    Path("claude_files/message_handler.py"),
    Path("backups/fix_20260721_235329/message_handler.py"),
    Path("backups/history_ban_fix_20260722_000952/message_handler.py"),
]

for src in sources:
    if src.exists():
        backup = target.with_name("message_handler.before_clean_restore.py")
        if target.exists():
            shutil.copy(target, backup)

        shutil.copy(src, target)

        print("✅ restored from:", src)
        print("backup:", backup)
        break
else:
    print("❌ backup not found")
