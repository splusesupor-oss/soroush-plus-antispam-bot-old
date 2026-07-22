from pathlib import Path
import re

p = Path("handlers/message_handler.py")
t = p.read_text(encoding="utf-8")

old = r'''await bot.admin_actions.delete_message\(
\s*chat_id,
\s*event=event
\s*\)'''

new = '''# حذف گروهی پیام های اسپم از تاریخچه
                  try:
                      ids = get_message_ids(chat_id, user_id)

                      if ids:
                          import asyncio

                          for i in range(0, len(ids), 100):
                              batch = ids[i:i+100]

                              try:
                                  await bot.client.delete_messages(
                                      chat_id,
                                      batch
                                  )
                              except Exception as ex:
                                  print("bulk delete error:", ex)

                              await asyncio.sleep(0.2)

                          clear_user(chat_id, user_id)

                      else:
                          await bot.admin_actions.delete_message(
                              chat_id,
                              event=event
                          )

                  except Exception as ex:
                      print("history delete error:", ex)'''

t2, n = re.subn(old, new, t)

if n:
    p.write_text(t2, encoding="utf-8")
    print("✅ bulk delete 100x added")
else:
    print("❌ block not found")
