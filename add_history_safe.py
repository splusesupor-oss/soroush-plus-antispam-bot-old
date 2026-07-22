from pathlib import Path
import shutil
from datetime import datetime

p = Path("handlers/message_handler.py")

backup = Path("backups") / f"before_history_safe_{datetime.now().strftime('%H%M%S')}.py"
shutil.copy(p, backup)
print("backup:", backup)

s = p.read_text(encoding="utf-8")

marker = "            is_spam, reason = bot.detector.is_spam(message_text, chat_id)"

insert = '''            # HISTORY REPEAT BAN SYSTEM
            try:
                add_message(chat_id, user_id, event.message.id, message_text)

                if is_repeat(chat_id, user_id, message_text):
                    print("🚨 HISTORY REPEAT BAN:", username, user_id)

                    ids = get_message_ids(chat_id, user_id)

                    if ids:
                        await bot.client.delete_messages(chat_id, ids)

                    await bot.admin_actions.ban_user(chat_id, user_id)

                    clear_user(chat_id, user_id)

                    return

            except Exception as e:
                print("history system error:", e)

'''

if "HISTORY REPEAT BAN SYSTEM" in s:
    print("already exists")
elif marker in s:
    s = s.replace(marker, insert + marker, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ history added")
else:
    print("❌ marker not found")
