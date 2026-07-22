from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

start = 0
end = 0

for i,l in enumerate(lines):
    if 'if repeat_found:' in l and i > 1300:
        start = i
        break

for i in range(start, len(lines)):
    if 'return' in lines[i] and i > start and 'except Exception as e:' in lines[i+1] if i+1 < len(lines) else False:
        end = i
        break

if not start or not end:
    print("FAIL")
    exit()

indent = "                                "

block = [
f"{indent}if repeat_found:",
f"{indent}    from modules.user_map import save_user",
f"{indent}    save_user(chat_id, username, user_id)",
"",
f"{indent}    try:",
f"{indent}        if not hasattr(bot, 'spammer_messages'):",
f"{indent}            bot.spammer_messages = {{}}",
"",
f"{indent}        bot.spammer_messages.setdefault(user_id, []).append(event.message.id)",
"",
f"{indent}        ids = bot.spammer_messages[user_id][:]",
f"{indent}        if ids:",
f"{indent}            await bot.client.delete_messages(chat_id, ids)",
"",
f"{indent}        bot.spammer_messages[user_id].clear()",
"",
f"{indent}    except Exception as e:",
f"{indent}        print('SPAM HISTORY ERROR:', e)",
"",
f"{indent}    print('🚨 HEAVY REPEAT SPAM BAN:', username, user_id)",
"",
f"{indent}    await bot.admin_actions.punish_user(chat_id, user_id, username)",
"",
f"{indent}    return"
]

lines[start:end+1] = block

p.write_text("\n".join(lines), encoding="utf-8")
print("OK")
