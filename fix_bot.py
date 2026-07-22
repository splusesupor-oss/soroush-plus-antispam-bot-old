from pathlib import Path
import shutil

p = Path("main.py")

if not p.exists():
    print("❌ main.py پیدا نشد")
    exit()

backup = Path("main.py.before_fix_ban_reset")
shutil.copy(p, backup)
print("✅ بکاپ ساخته شد:", backup)

s = p.read_text(encoding="utf-8")

# اصلاح اخراج: حذف remove_banned بعد از kick
old = '''try:
    remove_banned(
        chat_id,
        getattr(target_user, "username", "")
    )
except Exception:
    pass'''

if old in s:
    s = s.replace(old, '''try:
    add_banned(
        chat_id,
        getattr(target_user, "id", None)
    )
except Exception:
    pass''')
    print("✅ اصلاح بن دائمی انجام شد")
else:
    print("⚠️ بخش remove_banned اخراج پیدا نشد")

# اصلاح جستجوی username برای صفر کردن تخلف
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
    s = s.replace(old2, new2)
    print("✅ اصلاح صفر کردن تخلف انجام شد")
else:
    print("⚠️ بخش user_map پیدا نشد")

p.write_text(s, encoding="utf-8")
print("✅ تمام شد")
