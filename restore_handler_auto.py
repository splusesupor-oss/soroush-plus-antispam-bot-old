from pathlib import Path
import shutil

target = Path("handlers/message_handler.py")

candidates = [
    Path("handlers/message_handler.before_rebuild.py"),
    Path("main_error_backup.py"),
    Path("handlers/handle_new_message_restore.txt"),
]

handler = None

for f in candidates:
    if f.exists():
        text = f.read_text(encoding="utf-8")
        start = text.find("async def handle_new_message")
        if start != -1:
            handler = text[start:]
            print("FOUND:", f)
            break

if handler is None:
    print("❌ handler not found")
    exit()

backup = target.with_name("message_handler.before_handler_restore.py")
shutil.copy(target, backup)

text = target.read_text(encoding="utf-8")

start = text.find("async def handle_new_message")
if start != -1:
    text = text[:start]

target.write_text(text.rstrip()+"\n\n"+handler+"\n", encoding="utf-8")

print("✅ handle_new_message restored")
print("backup:", backup)
