from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

if "from modules.spam_history import" not in s:
    s = s.replace(
        "from pathlib import Path",
        "from modules.spam_history import add_message, is_repeat, get_message_ids, clear_user\nfrom pathlib import Path",
        1
    )

marker = "# بررسی اسپم"

block = '''
        # ذخیره تاریخچه پیام
        try:
            add_message(chat_id, user_id, event.message.id, message_text)
        except Exception as e:
            print("history save error:", e)

        # بن مستقیم بر اساس تاریخچه
        try:
            if is_repeat(chat_id, user_id, message_text):

                print("🚨 HISTORY DIRECT BAN:", username, user_id)

                ids = get_message_ids(chat_id, user_id)

                if ids:
                    await bot.client.delete_messages(
                        chat_id,
                        ids
                    )

                await bot.admin_actions.ban_user(
                    chat_id,
                    user_id
                )

                clear_user(
                    chat_id,
                    user_id
                )

                return

        except Exception as e:
            print("history ban error:", e)

'''

if "# ذخیره تاریخچه پیام" not in s:
    pos = s.find(marker)
    if pos != -1:
        s = s[:pos] + block + s[pos:]
    else:
        print("marker not found")

p.write_text(s, encoding="utf-8")

print("✅ history direct ban added")
