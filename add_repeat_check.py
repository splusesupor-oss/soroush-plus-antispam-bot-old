from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

marker = "        # بررسی اسپم"

block = '''
        # بررسی تاریخچه پیام‌های تکراری
        try:
            if is_repeat(chat_id, user_id, message_text):
                print("🚨 HISTORY REPEAT SPAM:", username, user_id)

                ids = get_message_ids(chat_id, user_id)

                if ids:
                    await bot.client.delete_messages(
                        chat_id,
                        ids
                    )

                clear_user(chat_id, user_id)

                bot.logger.log_deleted_message(
                    user_id=user_id,
                    username=username,
                    group_id=chat_id,
                    group_title=chat_title,
                    original_text=message_text,
                    reason="تکرار پیام در تاریخچه",
                    message_id=event.message.id
                )

                return

        except Exception as e:
            print("history repeat error:", e)

'''

if "HISTORY REPEAT SPAM" not in s:
    if marker in s:
        s=s.replace(marker, block+marker, 1)
        p.write_text(s, encoding="utf-8")
        print("✅ repeat history added")
    else:
        print("❌ marker not found")
else:
    print("already exists")
