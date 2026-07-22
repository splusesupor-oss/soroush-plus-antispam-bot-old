from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").expandtabs(4).splitlines()

start=1369   # خط 1370
end=1391     # قبل بررسی اسپم

block = """          # ذخیره تاریخچه پیام برای تشخیص تکرار
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
                      await bot.client.delete_messages(chat_id, ids)

                  await bot.admin_actions.ban_user(chat_id, user_id)

                  clear_user(chat_id, user_id)
                  return

          except Exception as e:
              print("history repeat error:", e)
""".splitlines()

lines[start:end]=block

# درست کردن خط بررسی اسپم
for i,l in enumerate(lines):
    if "# بررسی اسپم" in l:
        lines[i]="          # بررسی اسپم"
        break

p.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("✅ final history fixed")
