from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

start = None
end = None

for i,l in enumerate(lines):
    if "# بررسی تکرار شدید داخل یک پیام" in l:
        start = i
    if start and i > start and "# بررسی کلمات فیلتر شده گروه" in l:
        end = i
        break

if start is None or end is None:
    print("BLOCK NOT FOUND")
    exit()

new = '''            # بررسی تکرار شدید داخل یک پیام
            try:
                import re

                words = re.findall(r"\\w+|[آ-ی]+", message_text.lower())

                repeat_found = False

                for w in set(words):
                    if len(w) >= 3 and words.count(w) >= 8:
                        repeat_found = True
                        break

                if repeat_found:
                    from modules.user_map import save_user
                    save_user(chat_id, username, user_id)

                    try:
                        if not hasattr(bot, "spammer_messages"):
                            bot.spammer_messages = {}

                        bot.spammer_messages.setdefault(user_id, []).append(event.message.id)

                        ids = list(bot.spammer_messages[user_id])

                        if ids:
                            await bot.client.delete_messages(chat_id, ids)

                        bot.spammer_messages[user_id].clear()

                    except Exception as e:
                        print("SPAM HISTORY ERROR:", e)

                    print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                    try:
                        await bot.admin_actions.ban_user(chat_id, user_id)
                    except:
                        await bot.admin_actions.punish_user(chat_id, user_id, username)

                    return

            except Exception as e:
                bot.logger.log_error(f"خطای بررسی تکرار داخلی: {e}")

'''

lines[start:end] = new.splitlines()

p.write_text("\n".join(lines), encoding="utf-8")
print("RESTORED")
