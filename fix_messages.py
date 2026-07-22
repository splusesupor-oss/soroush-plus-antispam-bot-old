from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

# 1) اضافه کردن user_messages در __init__
old = '        self.flood_messages = {}\n'
new = '        self.flood_messages = {}\n        self.user_messages = {}\n'

if old in s and 'self.user_messages = {}' not in s:
    s = s.replace(old, new, 1)
    print("1 OK: user_messages added")
else:
    print("1 SKIP")


# 2) ذخیره پیام کاربر بعد از chat_id
old = '              chat_id = getattr(chat, "id", None)\n'
new = '''              chat_id = getattr(chat, "id", None)

              # ذخیره پیام‌های کاربران برای پاکسازی بعد از مجازات
              try:
                  if user_id and chat_id:
                      if chat_id not in self.user_messages:
                          self.user_messages[chat_id] = {}

                      if user_id not in self.user_messages[chat_id]:
                          self.user_messages[chat_id][user_id] = []

                      self.user_messages[chat_id][user_id].append(event.message.id)

                      if len(self.user_messages[chat_id][user_id]) > 300:
                          self.user_messages[chat_id][user_id] = self.user_messages[chat_id][user_id][-300:]

              except Exception as e:
                  self.logger.log_error(f"خطای ذخیره پیام کاربر: {e}")
'''

if old in s:
    s = s.replace(old, new, 1)
    print("2 OK: tracker added")
else:
    print("2 SKIP")


# 3) پاک کردن پیام‌ها قبل از punish_user
old = '                          await self.admin_actions.punish_user(chat_id, user_id, username)\n'

new = '''                          # پاک کردن پیام‌های قبلی کاربر قبل از مجازات
                          try:
                              old_ids = self.user_messages.get(chat_id, {}).get(user_id, [])

                              if old_ids:
                                  await self.client.delete_messages(chat_id, old_ids)

                              if chat_id in self.user_messages:
                                  self.user_messages[chat_id].pop(user_id, None)

                          except Exception as e:
                              self.logger.log_error(f"خطای پاکسازی پیام‌های کاربر: {e}")

                          await self.admin_actions.punish_user(chat_id, user_id, username)
'''

if old in s:
    s = s.replace(old, new, 1)
    print("3 OK: cleanup added")
else:
    print("3 SKIP")


p.write_text(s, encoding="utf-8")
print("DONE")
