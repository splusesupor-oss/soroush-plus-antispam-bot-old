from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

start=1239
end=1242

new=[
"            if len(user_msgs) >= 5:",
"                ids = [x[1] for x in user_msgs]",
"                try:",
"                    await bot.client.delete_messages(chat_id, ids)",
"                except Exception as e:",
"                    print('FLOOD DELETE ERROR:', e)",
"                bot.flood_messages[chat_id] = []",
"                return",
"",
]

lines[start:end]=new

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED 1240")
