from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")

backup=p.with_name("message_handler.py.before_history_delete_final")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

old='''                  if ids:
                      try:
                          print("🗑️ DELETING HISTORY:", len(ids))

                          for i in range(0, len(ids), 100):
                              batch = ids[i:i+100]
                              try:
                                  await bot.client.delete_messages(
                                      chat_id,
                                      batch
                                  )
                              except Exception as err:
                                  print("DELETE BATCH ERROR:", err)

                      except Exception as err:
                          print("DELETE HISTORY ERROR:", err)
'''

new='''                  if ids:
                      try:
                          print("🗑️ DELETING FULL HISTORY:", len(ids))

                          for i in range(0, len(ids), 100):
                              batch = ids[i:i+100]
                              try:
                                  await bot.client.delete_messages(
                                      chat_id,
                                      batch
                                  )
                              except Exception as err:
                                  print("DELETE BATCH ERROR:", err)

                      except Exception as err:
                          print("DELETE HISTORY ERROR:", err)

                  try:
                      await event.reply(
                          "⛔️ کاربر به دلیل اسپم مکرر حذف شد."
                      )
                  except Exception:
                      pass
'''

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ history delete fixed")
    print("backup:",backup)
else:
    print("❌ block not found")
    print("backup:",backup)
