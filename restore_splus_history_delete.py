from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

backup = Path("handlers/message_handler.py.before_restore_history_delete")
backup.write_text(text, encoding="utf-8")

old = """                          for i in range(0, len(ids), 100):
                              batch = ids[i:i+100]

                              try:
                                  await bot.client.delete_messages(
                                      chat_id,
                                      batch
                                  )
                              except Exception as ex:
                                  print("bulk history delete error:", ex)
"""

new = """                          for i in range(0, len(ids), 100):
                              batch = ids[i:i+100]

                              for msg_id in batch:
                                  try:
                                      await bot.client.delete_messages(
                                          chat_id,
                                          msg_id
                                      )
                                  except Exception as ex:
                                      print("history delete error:", ex)

                              import asyncio
                              await asyncio.sleep(0.2)
"""

if old in text:
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")
    print("✅ سروش پلاس: حذف پیام به حالت سازگار برگشت")
    print("backup:", backup)
else:
    print("❌ بخش حذف دسته‌ای پیدا نشد")
    print("backup:", backup)
