from pathlib import Path
import shutil

p=Path("modules/riddles.py")
s=p.read_text(encoding="utf-8")

shutil.copy2(p,"modules/riddles.py.before_user_fix")

s=s.replace(
    "active_riddles[(chat_id, 0)] = {",
    "active_riddles[(chat_id, user_id)] = {"
)

s=s.replace(
    "key = (chat_id, 0)",
    "key = (chat_id, user_id)"
)

s=s.replace(
    "data = active_riddles.get((chat_id, 0))",
    "data = active_riddles.get((chat_id, user_id))"
)

p.write_text(s,encoding="utf-8")

print("✅ ریدل به user_id وصل شد")
print("📦 بکاپ: modules/riddles.py.before_user_fix")
