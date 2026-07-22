from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

backup=Path("handlers/message_handler.before_history_indent_repair")
backup.write_text("\n".join(lines)+"\n",encoding="utf-8")

start=None
end=None

for i,l in enumerate(lines):
    if 'if is_repeat(chat_id, user_id, message_text):' in l:
        start=i
    if start and i>start and 'return' in l and l.strip()=="return":
        end=i
        break

if start is None or end is None:
    print("❌ block not found")
    exit()

new_block=[
"              if is_repeat(chat_id, user_id, message_text):",
"                  if getattr(bot, '_history_banned', None) == (chat_id, user_id):",
"                      return",
"",
"                  bot._history_banned = (chat_id, user_id)",
"",
"                  print('🚨 HISTORY REPEAT BAN:', user_id)",
"",
"                  ids = get_message_ids(chat_id, user_id)",
"",
"                  try:",
"                      for i in range(0, len(ids), 100):",
"                          batch = ids[i:i+100]",
"                          await bot.client.delete_messages(chat_id, batch)",
"                      print(f'🧹 ALL HISTORY DELETED | count={len(ids)}')",
"                  except Exception as err:",
"                      print('HISTORY DELETE ERROR:', err)",
"",
"                  try:",
"                      clear_user(chat_id, user_id)",
"                  except Exception as err:",
"                      print('CLEAR HISTORY ERROR:', err)",
"",
"                  print(f'🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}')",
"",
"                  try:",
"                      await bot.admin_actions.ban_user(chat_id, user_id)",
"                  except Exception as err:",
"                      print('BAN ERROR:', err)",
"",
"                  return"
]

lines[start:end+1]=new_block

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ history block rebuilt")
print("backup:",backup)
