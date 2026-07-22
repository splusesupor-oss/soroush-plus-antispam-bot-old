from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

imports = """
from modules.anti_attack import check_attack
from modules.security.media_spam import check_media_spam
from modules.security.delete_queue import add_delete
"""

if "from modules.anti_attack import check_attack" not in text:
    text = imports + "\n" + text

p.write_text(text, encoding="utf-8")

print("✅ security imports connected")
