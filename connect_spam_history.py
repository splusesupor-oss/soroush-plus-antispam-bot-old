from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

# import
if "from modules.spam_history import" not in text:
    text = text.replace(
        "from modules.user_map import save_user",
        "from modules.user_map import save_user\nfrom modules.spam_history import add_message, is_repeat, get_message_ids, clear_user",
        1
    )

# ثبت همه پیام‌ها
marker = "print(\"AUTO:\", repr(chat_id), type(chat_id), repr(user_id), type(user_id))"

if marker in text and "add_message(chat_id, user_id" not in text:
    text = text.replace(
        marker,
        marker +
        "\n            add_message(chat_id, user_id, event.message.id, message_text)",
        1
    )

p.write_text(text, encoding="utf-8")

print("✅ spam_history connected")
