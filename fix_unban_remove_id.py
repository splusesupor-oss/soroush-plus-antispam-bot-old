from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = "remove_banned(chat_id, username)"
new = "remove_banned(chat_id, user_id)"

count = text.count(old)

if count:
    text = text.replace(old,new)
    p.write_text(text,encoding="utf-8")
    print(f"✅ changed {count} remove_banned calls")
else:
    print("❌ not found")
