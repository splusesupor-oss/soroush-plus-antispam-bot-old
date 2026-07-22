from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

line = "from modules.security.media_spam import check_media_spam\n"

if line not in text:
    text = line + text

p.write_text(text, encoding="utf-8")

print("✅ media import connected")
