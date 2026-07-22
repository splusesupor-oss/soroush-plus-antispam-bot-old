from pathlib import Path
import re

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

start = text.find("# حذف گروهی پیام های اسپم از تاریخچه")
end = text.find('print("🚨 HEAVY REPEAT SPAM BAN:"', start)

if start == -1 or end == -1:
    print("❌ section پیدا نشد")
    exit()

block = '''# حذف گروهی پیام های اسپم از تاریخچه
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
                      print("history delete error:", ex)

'''

new = text[:start] + block + text[end:]

p.write_text(new, encoding="utf-8")

print("✅ bulk section replaced")
