from pathlib import Path

p = Path("handlers/message_handler.py")
s = p.read_text(encoding="utf-8")

old = '''          # بررسی اسپم
          if group_word_spam:
              is_spam = True
              reason = group_word_reason
          else:
              is_spam, reason = bot.detector.is_spam(message_text, chat_id)
'''

new = '''          # بررسی ادمین قبل از هر فیلتر
          try:
              from modules.admin_storage import is_admin

              if is_admin(chat_id, username):
                  print(f"✅ ADMIN BYPASS FILTER: {username}")
                  is_spam = False
                  reason = ""
              else:
                  if group_word_spam:
                      is_spam = True
                      reason = group_word_reason
                  else:
                      is_spam, reason = bot.detector.is_spam(message_text, chat_id)

          except Exception as e:
              print("ADMIN BYPASS ERROR:", e)

              if group_word_spam:
                  is_spam = True
                  reason = group_word_reason
              else:
                  is_spam, reason = bot.detector.is_spam(message_text, chat_id)
'''

if old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("✅ محافظ ادمین قبل از فیلتر اضافه شد")
else:
    print("❌ بلاک پیدا نشد")
