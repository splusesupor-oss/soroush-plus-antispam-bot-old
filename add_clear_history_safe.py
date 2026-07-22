from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

backup = Path("handlers/message_handler.py.before_clear_safe")
backup.write_text(text, encoding="utf-8")

marker = 'print("DELETE BATCH ERROR:", err)'

if marker in text:
    pos = text.find(marker)
    line_end = text.find("\n", pos)

    insert = '\n\n                          clear_user(chat_id, user_id)'

    text = text[:line_end] + insert + text[line_end:]

    p.write_text(text, encoding="utf-8")
    print("✅ clear_user added safely")
    print("backup:", backup)
else:
    print("❌ marker not found")
