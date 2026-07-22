from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

backup = Path("handlers/message_handler.before_fast_delete_batches")
backup.write_text(text, encoding="utf-8")

old = """for x in range(0, len(ids), 100):
                              batch = ids[x:x+100]
                              try:
                                  await bot.client.delete_messages(
                                      chat_id,
                                      batch
                                  )
                              except Exception as err:
                                  print('DELETE ERROR:', err)"""

new = """import asyncio

                          for x in range(0, len(ids), 100):
                              batch = ids[x:x+100]
                              try:
                                  await bot.client.delete_messages(
                                      chat_id,
                                      batch
                                  )
                                  await asyncio.sleep(0.2)
                              except Exception as err:
                                  print('DELETE ERROR:', err)"""

if old in text:
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")
    print("✅ fast batch delete 100 added")
    print("backup:", backup)
else:
    print("❌ block not found")
