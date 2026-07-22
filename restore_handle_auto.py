from pathlib import Path

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

if "async def handle_new_message" in text:
    print("✅ handle_new_message exists")
    exit()

backup = Path("handlers/message_handler.before_broken_top_fix.py")
old = backup.read_text(encoding="utf-8")

start = old.find("async def handle_new_message")

if start == -1:
    print("❌ handle_new_message not found in backup")
    exit()

handler = old[start:]

text = text + "\n\n" + handler

p.write_text(text, encoding="utf-8")

print("✅ handle_new_message restored")
