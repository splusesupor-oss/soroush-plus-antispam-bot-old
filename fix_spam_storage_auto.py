from pathlib import Path

p = Path("core/bot_working_split_ok.py")
text = p.read_text(encoding="utf-8")

# حذف نسخه خراب پایین فایل
start = text.find("# ---------- AUTO ADDED ----------")
if start != -1:
    text = text[:start]

# اضافه کردن توابع داخل کلاس قبل از run_until_disconnected
insert = """
    # ---------- SPAM HISTORY STORAGE ----------
    async def remember_spam_message(self, user_id, message_id):
        try:
            if not hasattr(self, "spammer_messages"):
                self.spammer_messages = {}

            if user_id not in self.spammer_messages:
                self.spammer_messages[user_id] = []

            self.spammer_messages[user_id].append(message_id)

        except Exception as e:
            print("remember spam error:", e)


    async def delete_all_spam_messages(self, user_id):
        try:
            ids = []

            if hasattr(self, "spammer_messages"):
                ids = list(self.spammer_messages.get(user_id, []))

            if ids:
                await self.client.delete_messages(ids)

            if hasattr(self, "spammer_messages"):
                self.spammer_messages.pop(user_id, None)

        except Exception as e:
            print("delete spam error:", e)

"""

target = "        await self.client.run_until_disconnected()"

if target in text:
    text = text.replace(target, insert + "\n" + target, 1)
else:
    print("❌ محل run پیدا نشد")
    exit()

# اضافه کردن فعال سازی حافظه در init
needle = "self.logger = BotLogger("

if needle in text and "self.spammer_messages" not in text:
    pos = text.find(needle)
    text = text[:pos] + "self.spammer_messages = {}\n        " + text[pos:]

p.write_text(text, encoding="utf-8")

print("✅ سیستم ذخیره و حذف اسپم اصلاح شد")
