from pathlib import Path
import shutil

src = Path("handlers/handle_new_message_restore.txt")
dst = Path("handlers/message_handler.py")

if not src.exists():
    print("❌ restore file not found")
    exit()

backup = Path("handlers/message_handler.before_restore_handler.py")
shutil.copy(dst, backup)

text = dst.read_text(encoding="utf-8")

old_start = text.find("async def handle_new_message")

if old_start != -1:
    text = text[:old_start]

handler = src.read_text(encoding="utf-8")

dst.write_text(
    text.rstrip() + "\n\n" + handler + "\n",
    encoding="utf-8"
)

print("✅ handler restored")
print("backup:", backup)
