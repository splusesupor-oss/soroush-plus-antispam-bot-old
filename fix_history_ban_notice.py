from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

backup = Path("handlers/message_handler.before_history_notice")
backup.write_text(text, encoding="utf-8")

old = '''print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")'''

new = '''print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")

                  try:
                      await bot.client.send_message(
                          chat_id,
                          f"⛔️ کاربر @{username or user_id} به دلیل اسپم مکرر حذف شد."
                      )
                  except Exception as err:
                      print("BAN NOTICE ERROR:", err)'''

if old in text:
    text = text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ history ban notice added")
    print("backup:",backup)
else:
    print("❌ marker not found")
