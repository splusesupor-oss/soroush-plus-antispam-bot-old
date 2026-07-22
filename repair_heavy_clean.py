from pathlib import Path

p=Path("handlers/message_handler.py")

lines=p.read_text(encoding="utf-8").splitlines()

start=None
end=None

for i,l in enumerate(lines):
    if l.strip()=="# بررسی تکرار شدید داخل یک پیام":
        start=i
    if start is not None and l.strip()=="group_word_spam = False":
        end=i
        break

if start is None or end is None:
    print("❌ markers not found")
    exit()

new_block = [
"        # بررسی تکرار شدید داخل یک پیام",
"        try:",
"            import re",
"",
"            words = re.findall(r'\\w+|[آ-ی]+', message_text.lower())",
"            repeat_found = False",
"",
"            for w in set(words):",
"                if len(w) >= 3 and words.count(w) >= 8:",
"                    repeat_found = True",
"                    break",
"",
"            if repeat_found:",
"                from modules.user_map import save_user",
"                save_user(chat_id, username, user_id)",
"",
"                print('🚨 HEAVY REPEAT SPAM:', username, user_id)",
"",
"                punish_key = f'{chat_id}:{user_id}'",
"",
"                if punish_key not in bot.punished_users:",
"                    bot.punished_users.add(punish_key)",
"",
"                    await bot.admin_actions.punish_user(",
"                        chat_id,",
"                        user_id,",
"                        username",
"                    )",
"",
"                return",
"",
"        except Exception as e:",
"            print('خطای بررسی تکرار شدید:', e)",
"",
]

lines = lines[:start] + new_block + lines[end:]

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ heavy block fully cleaned")
