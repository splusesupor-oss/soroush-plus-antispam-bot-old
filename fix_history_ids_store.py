from pathlib import Path

p=Path("modules/spam_history.py")
text=p.read_text(encoding="utf-8")

backup=Path("modules/spam_history.py.before_ids_fix")
backup.write_text(text,encoding="utf-8")

old="""USER_MESSAGE_IDS[key].append(message_id)"""

new="""if message_id not in USER_MESSAGE_IDS[key]:
        USER_MESSAGE_IDS[key].append(message_id)"""

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ message ids storage fixed")
    print("backup:",backup)
else:
    print("❌ append line not found")
