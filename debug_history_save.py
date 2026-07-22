from pathlib import Path

p=Path("modules/spam_history.py")
text=p.read_text(encoding="utf-8")

old='''    USER_MESSAGE_IDS[key].append(message_id)'''

new='''    USER_MESSAGE_IDS[key].append(message_id)
    print(f"💾 HISTORY COUNT user={user_id} count={len(USER_MESSAGE_IDS[key])}")'''

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ debug added")
else:
    print("❌ not found")
