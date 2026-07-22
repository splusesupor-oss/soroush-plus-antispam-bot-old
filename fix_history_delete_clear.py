from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = """                  print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")"""

new = """                  try:
                      clear_user(chat_id, user_id)
                      print(f"🧹 HISTORY CLEARED | user={user_id}")
                  except Exception as err:
                      print("CLEAR HISTORY ERROR:", err)

                  print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")"""

if old in text:
    text = text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ clear added")
else:
    print("❌ marker not found")
