from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

start = s.find("          try:\n              from modules.group_words_storage import get_words")
end = s.find("          # بررسی اسپم", start)

if start == -1 or end == -1:
    print("NOT FOUND")
    exit()

new = """          try:
              from modules.group_words_storage import get_words

              group_words = get_words(chat_id)

              for word in group_words:
                  if word and word in message_text:
                      group_word_spam = True
                      group_word_reason = f"فیلتر گروه ({word})"
                      break

          except Exception as e:
              bot.logger.log_error(f"خطای بررسی کلمات گروه: {e}")

          # ذخیره تاریخچه پیام
          try:
              add_message(chat_id, user_id, event.message.id, message_text)
          except Exception as e:
              print("history save error:", e)

          # تشخیص تکرار تاریخچه و بن مستقیم
          try:
              if is_repeat(chat_id, user_id, message_text):

                  print("🚨 HISTORY REPEAT BAN:", username, user_id)

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
              print("history repeat error:", e)

"""

s = s[:start] + new + s[end:]

p.write_text(s, encoding="utf-8")

print("AUTO REBUILT")
