from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
'''

new = '''                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                      asyncio.create_task(self.riddle_timeout_reply(event, chat_id, user_id))
'''

if old in s:
    s = s.replace(old, new, 1)
    print("✅ تایمر چیستان وصل شد")
else:
    print("❌ خط چیستان پیدا نشد")

p.write_text(s, encoding="utf-8")
