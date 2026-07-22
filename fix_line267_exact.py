from pathlib import Path

p = Path("main.py")
lines = p.read_text(encoding="utf-8").splitlines()

# خط 267 در خروجی nl است، در لیست پایتون ایندکس 266 است
lines[266] = "                      asyncio.create_task(self.riddle_timeout_reply(event, chat_id, user_id))"

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("✅ خط 267 دستی تنظیم شد")
