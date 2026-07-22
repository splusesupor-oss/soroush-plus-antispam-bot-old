from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

backup = p.with_name("message_handler.before_history_ban_delete_all")
shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

old = """                  print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")

                  try:
                      await bot.admin_actions.ban_user(
                          chat_id,
                          user_id
                      )
                  except Exception as err:
                      print("BAN ERROR:", err)
"""

new = """                  print(f"🚨 HISTORY SPAM DELETE ALL | chat={chat_id} user={user_id}")

                  try:
                      ids = get_message_ids(chat_id, user_id)

                      print("🗑️ DELETE COUNT:", len(ids))

                      for i in range(0, len(ids), 100):
                          batch = ids[i:i+100]

                          try:
                              await bot.client.delete_messages(
                                  chat_id,
                                  batch
                              )
                              print("✅ batch deleted:", len(batch))

                          except Exception as ex:
                              print("DELETE ERROR:", ex)

                      clear_user(chat_id, user_id)

                  except Exception as ex:
                      print("HISTORY CLEAN ERROR:", ex)


                  try:
                      await bot.admin_actions.ban_user(
                          chat_id,
                          user_id
                      )
                      print("🚫 USER BANNED")

                  except Exception as err:
                      print("BAN ERROR:", err)
"""

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ fixed")
    print("backup:",backup)
else:
    print("❌ block not found")
    print("backup:",backup)
