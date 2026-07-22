from pathlib import Path
import shutil
import re

target = Path("handlers/message_handler.py")

backup = Path("handlers/message_handler.before_broken_top_fix.py")

if not backup.exists():
    print("❌ backup not found")
    exit()

old = backup.read_text(encoding="utf-8")

m = re.search(
    r"(async def handle_new_message\(.*)",
    old,
    re.S
)

if not m:
    print("❌ handler in backup not found")
    exit()

handler = m.group(1)

text = target.read_text(encoding="utf-8")

if "async def handle_new_message" in text:
    print("✅ handler already exists")
    exit()

target.write_text(
    text.rstrip() + "\n\n" + handler,
    encoding="utf-8"
)

print("✅ handle_new_message restored")
