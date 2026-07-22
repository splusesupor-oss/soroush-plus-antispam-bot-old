from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_history_block_repair")
backup.write_text(text,encoding="utf-8")

start=text.find("        # ذخیره تاریخچه پیام برای ضد تکرار")
end=text.find("        # جستجوی وب", start)

if start == -1 or end == -1:
    print("❌ markers not found")
    exit()

new_block='''        # ذخیره تاریخچه پیام برای ضد تکرار
        try:
            save_history_message(
                chat_id,
                user_id,
                event.message.id,
                message_text
            )

            if is_repeat(chat_id, user_id, message_text):
                if getattr(bot, "_history_banned", None) == (chat_id, user_id):
                    return

                bot._history_banned = (chat_id, user_id)

                print("🚨 HISTORY REPEAT BAN:", user_id)

                ids = get_message_ids(chat_id, user_id)

                if ids:
                    try:
                        await bot.client.delete_messages(
                            chat_id,
                            ids
                        )
                        print(f"🧹 ALL HISTORY DELETED | count={len(ids)}")

                    except Exception as err:
                        print("HISTORY DELETE ERROR:", err)

                clear_user(chat_id, user_id)

                try:
                    await bot.admin_actions.ban_user(
                        chat_id,
                        user_id
                    )
                except Exception as err:
                    print("BAN ERROR:", err)

                try:
                    await bot.client.send_message(
                        chat_id,
                        f"⛔️ کاربر @{username or user_id} به دلیل اسپم مکرر حذف شد."
                    )
                except:
                    pass

                return

        except Exception as e:
            print("HISTORY ERROR:", e)

'''

text=text[:start]+new_block+text[end:]

p.write_text(text,encoding="utf-8")

print("✅ history block repaired")
print("backup:",backup)
