from pathlib import Path
import shutil
import re

src = Path("main_error_backup.py")
dst = Path("handlers/message_handler.py")

backup = Path("handlers/message_handler.before_rebuild.py")
shutil.copy(dst, backup)

old = src.read_text(encoding="utf-8", errors="ignore")

m1 = re.search(r"(async def handle_new_message\(.*?)(?=\n\s*async def |\Z)", old, re.S)

if not m1:
    print("❌ handle_new_message not found")
    exit()

handler = m1.group(1)

text = dst.read_text(encoding="utf-8", errors="ignore")

start = text.find("async def handle_new_message")

if start != -1:
    end = text.find("\n    async def ", start + 10)
    if end == -1:
        text = text[:start]
    else:
        text = text[:start] + text[end:]

text = text.rstrip() + "\n\n" + handler.rstrip() + "\n"

dst.write_text(text, encoding="utf-8")

print("✅ rebuilt")
print("backup:", backup)
