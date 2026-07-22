from pathlib import Path
import shutil

p = Path("main.py")

backup = Path("main.py.before_ban_line_fix")
shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

old = "if is_banned(chat_id, user_id) or (username and is_banned(chat_id, username)):"
new = "if is_banned(chat_id, user_id, username):"

if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ خط بن اصلاح شد")
else:
    print("❌ خط پیدا نشد")

print("بکاپ:", backup)
