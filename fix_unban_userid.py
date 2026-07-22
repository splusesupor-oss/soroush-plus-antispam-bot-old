from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

text = text.replace(
    "remove_banned(chat_id, user_id)",
    "remove_banned(chat_id, user.id)"
)

p.write_text(text, encoding="utf-8")

print("✅ unban userid fixed")
