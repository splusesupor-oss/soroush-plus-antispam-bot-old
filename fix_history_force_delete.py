from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_force_delete")
backup.write_text(text,encoding="utf-8")

old='''clear_user(chat_id, user_id)'''

new='''await bot.client.delete_messages(
                              chat_id,
                              ids
                          )

                          clear_user(chat_id, user_id)
                          print(f"🧹 ALL HISTORY DELETED | user={user_id}")'''

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ force history delete fixed")
    print("backup:",backup)
else:
    print("❌ clear_user not found")
