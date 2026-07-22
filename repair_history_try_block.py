from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

start=None
end=None

for i,l in enumerate(lines):
    if "💾 HISTORY COUNT" in l or "try:" in l and i>130 and i<170:
        start=i
        break

for i in range(start or 0,len(lines)):
    if "if clean_text.startswith" in lines[i]:
        end=i
        break

if start is None or end is None:
    print("❌ block not found")
    exit()

backup=Path("handlers/message_handler.before_try_repair")
backup.write_text("\n".join(lines)+"\n",encoding="utf-8")

new_block=[
"        try:",
"            save_history_message(chat_id, user_id, event.message.id, message_text)",
"",
"            if is_repeat(chat_id, user_id, message_text):",
"                ids = get_message_ids(chat_id, user_id)",
"",
"                print(f'🚨 HISTORY REPEAT BAN: {user_id}')",
"                print(f'🧹 DELETING HISTORY COUNT: {len(ids)}')",
"",
"                for i in range(0, len(ids), 100):",
"                    batch = ids[i:i+100]",
"                    try:",
"                        await bot.client.delete_messages(chat_id, batch)",
"                    except Exception as err:",
"                        print('DELETE ERROR:', err)",
"",
"                clear_user(chat_id, user_id)",
"                print(f'🧹 ALL HISTORY DELETED | count={len(ids)}')",
"",
"                try:",
"                    await bot.admin_actions.ban_user(chat_id,user_id)",
"                except Exception as err:",
"                    print('BAN ERROR:',err)",
"",
"                return",
"",
"        except Exception as e:",
"            print('HISTORY ERROR:',e)"
]

lines = lines[:start] + new_block + [""] + lines[end:]

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ history try block repaired")
print("backup:",backup)
