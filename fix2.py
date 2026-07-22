from pathlib import Path
import shutil

p = Path("main.py")

if not p.exists():
    print("❌ main.py نیست")
    exit()

s = p.read_text(encoding="utf-8")

# اصلاح remove_banned مربوط به اخراج با ریپلای (فقط همان بخش)
old = '''remove_banned(
                            chat_id,
                            getattr(target_user, "username", "")
                        )'''

new = '''add_banned(
                            chat_id,
                            getattr(target_user, "id", None)
                        )'''

if old in s:
    s = s.replace(old, new, 1)
    print("✅ بن دائمی اصلاح شد")
else:
    print("⚠️ بخش بن پیدا نشد")

# اصلاح پیدا کردن کاربر برای صفر تخلف
old2 = '''if username.lower() in users:
                                user_id = int(users[username.lower()])
                                break'''

new2 = '''for key, value in users.items():
                                if str(key).replace("@", "").lower() == username.replace("@", "").lower():
                                    user_id = int(value)
                                    break
                            if user_id:
                                break'''

if old2 in s:
    s = s.replace(old2, new2, 1)
    print("✅ صفر کردن تخلف اصلاح شد")
else:
    print("⚠️ بخش user_map پیدا نشد")

p.write_text(s, encoding="utf-8")
print("✅ پایان اصلاح")
