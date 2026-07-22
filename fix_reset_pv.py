from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_reset_pv_fix"

shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

old = '''                        for gid, users in user_map.items():
                            if username.lower() in users:
                                user_id = int(users[username.lower()])
                                break
'''

new = '''                        for gid, users in user_map.items():
                            for uname, uid in users.items():
                                if str(uname).lower() == username.lower():
                                    user_id = int(uid)
                                    break
                            if user_id:
                                break
'''

if old not in s:
    print("❌ بخش مورد نظر پیدا نشد، تغییری انجام نشد")
    print("بکاپ:", backup)
    exit()

s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")

print("✅ فقط بخش پیدا کردن کاربر در صفر کردن پیوی اصلاح شد")
print("📦 بکاپ:", backup)
