from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

old = '''        clean_text = message_text.strip()
'''

new = '''        clean_text = message_text.strip()

        # ذخیره تاریخچه پیام برای ضد تکرار
        try:
            save_history_message(
                chat_id,
                user_id,
                event.message.id,
                message_text
            )

            if is_repeat(chat_id, user_id, message_text):
                print("🚨 HISTORY REPEAT BAN:", user_id)

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

                clear_user(chat_id, user_id)
                return

        except Exception as e:
            print("history error:", e)
'''

if old not in s:
    print("❌ marker not found")
else:
    s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("✅ history call added")
