python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''              # ضد اسپم پیام‌های پشت سرهم
              try:
                  import time

                  if not hasattr(self, "flood_messages"):
                      self.flood_messages = {}

                  if chat_id not in self.flood_messages:
                      self.flood_messages[chat_id] = []

                  self.flood_messages[chat_id].append(
                      (time.time(), event.message.id)
                  )

                  now = time.time()

                  self.flood_messages[chat_id] = [
                      x for x in self.flood_messages[chat_id]
                      if now - x[0] <= 10
                  ]

                  if len(self.flood_messages[chat_id]) >= 5:
                      ids = [
                          x[1]
                          for x in self.flood_messages[chat_id]
                      ]

                      await self.client.delete_messages(
                          chat_id,
                          ids
                      )

                      self.flood_messages[chat_id] = []

                      if chat_id not in self.delete_notice_lock:
                          self.delete_notice_lock.add(chat_id)
                          await event.reply(
                              "⚠️ ارسال پیام‌های زیاد پشت سرهم حذف شد"
                          )

                      return
'''

new='''              # ضد فلود هوشمند بر اساس هر کاربر
              try:
                  import time

                  if not hasattr(self, "flood_messages"):
                      self.flood_messages = {}

                  flood_key = f"{chat_id}:{user_id}"

                  if flood_key not in self.flood_messages:
                      self.flood_messages[flood_key] = []

                  self.flood_messages[flood_key].append(
                      (time.time(), event.message.id)
                  )

                  now = time.time()

                  self.flood_messages[flood_key] = [
                      x for x in self.flood_messages[flood_key]
                      if now - x[0] <= 10
                  ]

                  # فقط یک کاربر با 20 پیام در 10 ثانیه فلود محسوب شود
                  if len(self.flood_messages[flood_key]) >= 20:
                      ids = [
                          x[1]
                          for x in self.flood_messages[flood_key]
                      ]

                      await self.client.delete_messages(
                          chat_id,
                          ids
                      )

                      self.flood_messages[flood_key] = []

                      await event.reply(
                          "⚠️ ارسال پیام‌های زیاد پشت سرهم حذف شد"
                      )

                      return
'''

if old not in s:
    print("target not found")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("flood fixed per user")

PY

python3 -m py_compile main.py && echo "syntax ok"
