from pathlib import Path

p = Path("modules/riddles.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
"active_riddles[(chat_id, user_id)] = {",
"active_riddles[(chat_id, 0)] = {"
)

s = s.replace(
"key = (chat_id, user_id)",
"key = (chat_id, 0)"
)

s = s.replace(
"active_riddles.get((chat_id, user_id))",
"active_riddles.get((chat_id, 0))"
)

p.write_text(s, encoding="utf-8")
print("✅ جواب چیستان برای کل گروه فعال شد")
