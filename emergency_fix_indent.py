from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

# پیدا کردن محدوده خراب با شماره خط فعلی
start = None
end = None

for i,l in enumerate(lines):
    if "if repeat_found:" in l and i > 1300:
        start = i-10
    if start and i > start and "# بررسی کلمات فیلتر شده گروه" in l:
        end = i
        break

if start is None or end is None:
    print("RANGE NOT FOUND")
    print("try:")
    for i,l in enumerate(lines):
        if "repeat_found" in l or "بررسی کلمات فیلتر" in l:
            print(i+1, repr(l))
    exit()

block = [
"        # بررسی تکرار شدید داخل یک پیام",
"        try:",
"            import re",
"",
"            words = re.findall(r'\\w+|[آ-ی]+', message_text.lower())",
"            repeat_found = any(len(w) >= 3 and words.count(w) >= 8 for w in set(words))",
"",
"            if repeat_found:",
"                from modules.user_map import save_user",
"                save_user(chat_id, username, user_id)",
"",
"                await bot.admin_actions.delete_message(chat_id, event=event)",
"                print('🚨 HEAVY REPEAT SPAM BAN:', username, user_id)",
"",
"                await bot.admin_actions.punish_user(",
"                    chat_id,",
"                    user_id,",
"                    username",
"                )",
"                return",
"",
"        except Exception as e:",
"            bot.logger.log_error(f'خطای بررسی تکرار داخلی: {e}')",
""
]

lines[start:end] = block

p.write_text("\n".join(lines), encoding="utf-8")
print("DONE")
