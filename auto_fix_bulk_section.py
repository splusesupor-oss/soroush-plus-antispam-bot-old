from pathlib import Path

p = Path("handlers/message_handler.py")

backup = Path("handlers/message_handler_before_bulk_auto_fix.py")
backup.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

lines = p.read_text(encoding="utf-8").splitlines()

start = None
end = None

for i,l in enumerate(lines):
    if "# حذف گروهی پیام های اسپم از تاریخچه" in l:
        start = i
    if start is not None and 'print("🚨 HEAVY REPEAT SPAM BAN"' in l:
        end = i
        break

if start is None or end is None:
    print("❌ block پیدا نشد")
    exit()

block = [
"                  # حذف گروهی پیام های اسپم از تاریخچه",
"                  try:",
"                      ids = get_message_ids(chat_id, user_id)",
"",
"                      if ids:",
"                          import asyncio",
"",
"                          for i in range(0, len(ids), 100):",
"                              batch = ids[i:i+100]",
"",
"                              try:",
"                                  await bot.client.delete_messages(chat_id, batch)",
"                              except Exception as ex:",
"                                  print('bulk delete error:', ex)",
"",
"                              await asyncio.sleep(0.2)",
"",
"                          clear_user(chat_id, user_id)",
"",
"                      else:",
"                          await bot.admin_actions.delete_message(",
"                              chat_id,",
"                              event=event",
"                          )",
"",
"                  except Exception as ex:",
"                      print('history delete error:', ex)"
]

new_lines = lines[:start] + block + lines[end:]

p.write_text("\n".join(new_lines)+"\n", encoding="utf-8")

print("✅ bulk section repaired automatically")
print("backup:", backup)
