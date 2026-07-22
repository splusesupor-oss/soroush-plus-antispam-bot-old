from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''if len(self.flood_messages[user_id]) >= 5:
                    ids = [
                        x[1]
                        for x in self.flood_messages[user_id]
                    ]

                    await self.client.delete_messages(
                        chat_id,
                        ids
                    )

                    self.flood_messages[user_id] = []

                    await event.reply(
                        "⚠️ ارسال پیام‌های زیاد پشت سرهم حذف شد"
                    )

                    return'''

new = '''if len(self.flood_messages[user_id]) >= 20:
                    ids = [
                        x[1]
                        for x in self.flood_messages[user_id]
                    ]

                    try:
                        await self.client.delete_messages(chat_id, ids)
                    except:
                        pass

                    self.flood_messages[user_id] = []

                    print("🚨 اسپمر رگباری:", user_id)

                    try:
                        await self.admin_actions.punish_user(
                            chat_id,
                            user_id,
                            username
                        )
                    except Exception as e:
                        self.logger.log_error(
                            f"خطای ریم اسپمر سریع: {e}"
                        )

                    return'''

if old in s:
    s=s.replace(old,new)
else:
    print("بخش فلود پیدا نشد")

p.write_text(s,encoding="utf-8")
print("✅ FIX DONE")
