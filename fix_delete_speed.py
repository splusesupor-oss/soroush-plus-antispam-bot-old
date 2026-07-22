from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_delete_speed")
backup.write_text(text,encoding="utf-8")

old="""print(f"🧹 ALL HISTORY DELETED | count={len(ids)}")"""

new="""clear_user(chat_id, user_id)
print(f"🧹 ALL HISTORY DELETED | count={len(ids)}")"""

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ clear after delete added")
else:
    print("❌ marker not found")
