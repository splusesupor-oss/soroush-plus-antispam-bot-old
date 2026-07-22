import shutil

f="main.py"
backup="main.py.before_remove_call_fix"

shutil.copy(f,backup)

s=open(f,encoding="utf-8").read()

old="remove_banned(chat_id, username)"
new="remove_banned(chat_id, user_id)"

if old in s:
    s=s.replace(old,new)
    open(f,"w",encoding="utf-8").write(s)
    print("✅ فراخوانی remove_banned اصلاح شد")
    print("📦 بکاپ:",backup)
else:
    print("❌ خط پیدا نشد")
