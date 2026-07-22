from pathlib import Path
import shutil, datetime

p = Path("handlers/message_handler.py")

backup = Path("backups") / ("history_marker_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(parents=True, exist_ok=True)
shutil.copy(p, backup / "message_handler.py")

print("✅ backup:", backup)

lines = p.read_text(encoding="utf-8").splitlines()

start = None
end = None

for i, line in enumerate(lines):
    if "# بررسی تاریخچه پیام‌های تکراری" in line:
        start = i
    if start is not None and 'print("history repeat error:", e)' in line:
        end = i + 1
        break

if start is None or end is None:
    print("❌ بخش تاریخچه پیدا نشد")
    exit()

new_block = '''          # بررسی تاریخچه پیام‌های تکراری
          try:
              if is_repeat(chat_id, user_id, message_text):
                  print("🚨 HISTORY REPEAT BAN:", username, user_id)

                  ids = get_message_ids(chat_id, user_id)

                  if ids:
                      await bot.client.delete_messages(
                          chat_id,
                          ids
                      )

                  if hasattr(bot.admin_actions, "ban_user"):
                      await bot.admin_actions.ban_user(
                          chat_id,
                          user_id
                      )

                  clear_user(chat_id, user_id)

                  print("✅ HISTORY DELETE + BAN DONE")

                  return

          except Exception as e:
              print("history repeat error:", e)'''.splitlines()

lines[start:end] = new_block

p.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("✅ history block replaced")
