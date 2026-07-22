from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")

text=p.read_text(encoding="utf-8")

backup="handlers/message_handler.py.before_outer_structure_fix"
shutil.copy(p, backup)

start=text.find("# بررسی تکرار شدید داخل یک پیام")
end=text.find("# دستورات مدیریت کلمات نباید توسط فیلتر گرفته شوند")

if start==-1 or end==-1:
    print("❌ markers not found")
    exit()

new=r'''        # بررسی تکرار شدید داخل یک پیام
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

                print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                punish_key=f"{chat_id}:{user_id}"

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


        group_word_spam = False
        group_word_reason = None

'''

text=text[:start]+new+text[end:]

p.write_text(text,encoding="utf-8")

print("✅ outer structure fixed")
print("backup:",backup)
