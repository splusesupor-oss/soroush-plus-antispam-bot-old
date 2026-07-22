from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = "from modules.spam_history import save_history_message, is_repeat, get_message_ids, clear_user"

if "clear_user" not in text.split("\n")[1]:
    text = text.replace(
        "from modules.spam_history import save_history_message, is_repeat, get_message_ids",
        "from modules.spam_history import save_history_message, is_repeat, get_message_ids, clear_user",
        1
    )

p.write_text(text, encoding="utf-8")
print("✅ clear_user import fixed")
