from pathlib import Path
import shutil
import datetime

file = Path("handlers/message_handler.py")

if not file.exists():
    print("❌ فایل پیدا نشد")
    exit()

# بکاپ
backup_dir = Path("backups") / ("history_ban_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_dir.mkdir(parents=True, exist_ok=True)

shutil.copy(
    file,
    backup_dir / "message_handler.py"
)

print("✅ بکاپ ساخته شد:", backup_dir)


text = file.read_text(encoding="utf-8")


old = '''if is_repeat(chat_id, user_id, message_text):
                print("🚨 HISTORY REPEAT SPAM:", username, user_id)

                ids = get_message_ids(chat_id, user_id)

                if ids:
                    await bot.client.delete_messages(
                        chat_id,
                        ids
                    )

                clear_user(chat_id, user_id)

                return'''


new = '''if is_repeat(chat_id, user_id, message_text):
                print("🚨 HISTORY REPEAT BAN:", username, user_id)

                try:
                    ids = get_message_ids(chat_id, user_id)

                    # حذف تمام پیام های ذخیره شده کاربر
                    if ids:
                        await bot.client.delete_messages(
                            chat_id,
                            ids
                        )

                    # بن مستقیم بدون امتیاز
                    if hasattr(bot.admin_actions, "ban_user"):
                        await bot.admin_actions.ban_user(
                            chat_id,
                            user_id
                        )

                    # پاک کردن تاریخچه
                    clear_user(chat_id, user_id)

                    print("✅ history deleted + banned")

                except Exception as e:
                    print("history ban error:", e)

                return'''


if old in text:
    text = text.replace(old, new, 1)
    file.write_text(text, encoding="utf-8")
    print("✅ سیستم تاریخچه به بن مستقیم تغییر کرد")
else:
    print("⚠️ بلاک قدیمی پیدا نشد")

