from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

start = None
end = None

for i,l in enumerate(lines):
    if "# بررسی تاریخچه پیام‌های تکراری" in l:
        start = i
    if start is not None and "# بررسی اسپم" in l:
        end = i
        break

if start is None or end is None:
    print("❌ marker not found")
    exit()

block = [
"          # بررسی تاریخچه پیام‌های تکراری",
"          try:",
"              if is_repeat(chat_id, user_id, message_text):",
"                  print(\"🚨 HISTORY REPEAT BAN:\", username, user_id)",
"",
"                  ids = get_message_ids(chat_id, user_id)",
"",
"                  if ids:",
"                      await bot.client.delete_messages(",
"                          chat_id,",
"                          ids",
"                      )",
"",
"                  if hasattr(bot.admin_actions, \"ban_user\"):",
"                      await bot.admin_actions.ban_user(",
"                          chat_id,",
"                          user_id",
"                      )",
"",
"                  clear_user(chat_id, user_id)",
"",
"                  print(\"✅ HISTORY DELETE + BAN DONE\")",
"",
"                  return",
"",
"          except Exception as e:",
"              print(\"history repeat error:\", e)",
""
]

lines[start:end] = block + [""]

p.write_text("\n".join(lines)+"\n", encoding="utf-8")

print("✅ block rewritten")
