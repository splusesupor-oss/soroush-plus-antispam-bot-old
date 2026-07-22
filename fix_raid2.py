from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

target = '''print("🚨 اسپمر رگباری:", user_id)
                try:
                    removed = await self.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username
                    )

                    if removed:
                        try:
                            await self.client.send_message(
                                chat_id,
                                f"⛔️ کاربر @{username or user_id} به دلیل ارسال اسپم رگباری حذف شد."
                            )
                        except:
                            pass'''

pos = s.find('print("🚨 اسپمر رگباری:", user_id)')

if pos == -1:
    print("❌ متن پیدا نشد")
    exit()

end = s.find('                except Exception as e:', pos)

if end == -1:
    print("❌ انتهای بخش پیدا نشد")
    exit()

new = '''print("🚨 اسپمر رگباری:", user_id)

                if not hasattr(self, "raid_removed"):
                    self.raid_removed = set()

                raid_key = f"{chat_id}:{user_id}"

                if raid_key in self.raid_removed:
                    return

                self.raid_removed.add(raid_key)

                try:
                    removed = await self.admin_actions.punish_user(
                        chat_id,
                        user_id,
                        username
                    )

                    if removed:
                        try:
                            await self.client.send_message(
                                chat_id,
                                f"⛔️ کاربر @{username or user_id} به دلیل ارسال اسپم رگباری حذف شد."
                            )
                        except:
                            pass

'''

s = s[:pos] + new + s[end:]

p.write_text(s, encoding="utf-8")
print("✅ اصلاح شد")
