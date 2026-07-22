from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

start = s.find("# ذخیره تاریخچه پیام برای تشخیص تکرار")
end = s.find("# بررسی اسپم", start)

if start == -1 or end == -1:
    print("❌ markers not found")
    exit()

old = s[start:end]

new = '''# ذخیره تاریخچه پیام برای تشخیص تکرار
          try:
              add_message(chat_id, user_id, event.message.id, message_text)
          except Exception as e:
              print("history save error:", e)

          # بررسی تاریخچه پیام‌های تکراری
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
              print("history repeat error:", e)

'''

s = s[:start] + new + s[end:]

p.write_text(s, encoding="utf-8")

print("✅ history section rebuilt")
