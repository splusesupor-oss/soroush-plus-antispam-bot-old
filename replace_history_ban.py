from pathlib import Path
import shutil
import datetime

p = Path("handlers/message_handler.py")

backup = Path("backups") / ("history_ban_fix_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(parents=True, exist_ok=True)

shutil.copy(p, backup / "message_handler.py")
print("✅ backup:", backup)

s = p.read_text(encoding="utf-8")

old = '''          # بررسی تاریخچه پیام‌های تکراری
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
'''

new = '''          # بررسی تاریخچه پیام‌های تکراری
          try:
              if is_repeat(chat_id, user_id, message_text):
                  print("🚨 HISTORY REPEAT BAN:", username, user_id)

                  ids = get_message_ids(chat_id, user_id)

                  # حذف همه پیام‌های ذخیره شده کاربر
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

                  print("✅ HISTORY DELETE + BAN DONE")

                  return
'''

if old not in s:
    print("❌ بلاک پیدا نشد")
    exit()

s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")

print("✅ history system updated")
