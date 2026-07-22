import re, shutil

f="modules/banned_storage.py"
backup=f+".before_remove_fix"

shutil.copy(f,backup)

s=open(f,encoding="utf-8").read()

pattern=r"def remove_banned\(group_id, username\):.*?return False"

replacement="""def remove_banned(group_id, user_id):
    data = load_banned()
    gid = str(group_id)
    uid = str(user_id)

    if gid in data:
        for x in list(data[gid]):
            if str(x) == uid:
                data[gid].remove(x)
                save_banned(data)
                return True

    return False"""

new,n=re.subn(pattern,replacement,s,flags=re.S)

if n:
    open(f,"w",encoding="utf-8").write(new)
    print("✅ اصلاح شد")
    print("📦 بکاپ:",backup)
else:
    print("❌ پیدا نشد")

