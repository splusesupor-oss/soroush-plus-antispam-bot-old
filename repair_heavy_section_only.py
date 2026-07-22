from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

start = text.find("# بررسی تکرار شدید داخل یک پیام")
end = text.find("group_word_spam = False")

if start == -1 or end == -1:
    print("❌ markers not found")
    exit()

backup = "handlers/message_handler.py.before_heavy_section_replace"
shutil.copy(p, backup)

new_block = r'''# بررسی تکرار شدید داخل یک پیام
try:
    import re

    words = re.findall(r"\w+|[آ-ی]+", message_text.lower())
    repeat_found = False

    for w in set(words):
        if len(w) >= 3 and words.count(w) >= 8:
            repeat_found = True
            break

    if repeat_found:
        from modules.user_map import save_user

        save_user(chat_id, username, user_id)

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

        print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

        punish_key = f"{chat_id}:{user_id}"

        if punish_key not in bot.punished_users:
            bot.punished_users.add(punish_key)

            await bot.admin_actions.punish_user(
                chat_id,
                user_id,
                username
            )

        return

except Exception as e:
    print("خطای بررسی تکرار شدید:", e)

'''

text = text[:start] + new_block + text[end:]

p.write_text(text, encoding="utf-8")

print("✅ heavy section replaced")
print("backup:", backup)
