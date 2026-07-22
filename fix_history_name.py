from pathlib import Path

p=Path("modules/spam_history.py")
s=p.read_text(encoding="utf-8")

s=s.replace(
"def add_message(chat_id, user_id, message_id, text):",
"def save_history_message(chat_id, user_id, message_id, text):"
)

p.write_text(s,encoding="utf-8")


p=Path("handlers/message_handler.py")
s=p.read_text(encoding="utf-8")

s=s.replace(
"from modules.spam_history import add_message, is_repeat, get_message_ids, clear_user",
"from modules.spam_history import save_history_message, is_repeat, get_message_ids, clear_user"
)

s=s.replace(
"add_message(chat_id, user_id, event.message.id, message_text)",
"save_history_message(chat_id, user_id, event.message.id, message_text)"
)

p.write_text(s,encoding="utf-8")

print("✅ history name separated")
