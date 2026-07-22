#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''                self.flood_messages[chat_id].append(
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

new = '''                self.flood_messages[chat_id].append(
                    (
                        time.time(),
                        event.message.id,
                        user_id,
                        message_text.strip()
                    )
                )

                now = time.time()

                self.flood_messages[chat_id] = [
                    x for x in self.flood_messages[chat_id]
                    if now - x[0] <= 10
                ]

                user_msgs = [
                    x for x in self.flood_messages[chat_id]
                    if x[2] == user_id
                ]

                # فقط پیام‌های تکراری یک کاربر حذف شوند
                if len(user_msgs) >= 5:

                    texts = [
                        x[3]
                        for x in user_msgs
                    ]

                    normalized = [
                        t.replace(" ", "")
                         .replace("\\n", "")
                        for t in texts
                    ]

                    # پیام‌های متفاوت مکالمه عادی هستند
                    if len(set(normalized)) > 2:
                        return

                    ids = [
                        x[1]
                        for x in user_msgs
                    ]

                    await self.client.delete_messages(
                        chat_id,
                        ids
                    )

                    self.flood_messages[chat_id] = []

                    if chat_id not in self.delete_notice_lock:
                        self.delete_notice_lock.add(chat_id)
                        await event.reply(
                            "⚠️ ارسال پیام تکراری پشت سرهم حذف شد"
                        )

                    return
'''

if old not in s:
    print("❌ بخش قدیمی پیدا نشد، هیچ تغییری انجام نشد")
else:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("✅ flood fix applied")

PY

python3 -m py_compile main.py && echo "✅ syntax ok"
