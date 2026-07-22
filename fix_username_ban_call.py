from pathlib import Path
import shutil

p = Path("main.py")

if not p.exists():
    print("❌ main.py پیدا نشد")
    exit()

backup = Path("main.py.before_username_ban_call")

shutil.copy(p, backup)
print("✅ بکاپ ساخته شد:", backup)

s = p.read_text(encoding="utf-8")

old = "if is_banned(chat_id, user_id):"
new = 'if is_banned(chat_id, user_id, getattr(user, "username", None)):'

if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ خط is_banned اصلاح شد")
else:
    print("⚠️ خط موردنظر پیدا نشد، تغییری انجام نشد")

