from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
'                    asyncio.create_task(self.riddle_timeout_reply(event, chat_id, user_id))',
'                      asyncio.create_task(self.riddle_timeout_reply(event, chat_id, user_id))'
)

p.write_text(s, encoding="utf-8")
print("✅ خط 267 درست شد")
