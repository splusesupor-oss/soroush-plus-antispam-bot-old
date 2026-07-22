#!/data/data/com.termux/files/usr/bin/bash

cp main.py main.py.before_banned_admin_lock

python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

old='''        if text == "لغو کلمات ممنوعه":
            disable(chat_id)
            await event.respond("✅ کلمات ممنوعه برای این گروه خاموش شد")
            return

        if text == "فعال کلمات ممنوعه":
            enable(chat_id)
            await event.respond("✅ کلمات ممنوعه برای این گروه فعال شد")
            return

'''

new=''''''

if old not in s:
    print("TARGET NOT FOUND")
else:
    s=s.replace(old,new,1)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile main.py && echo "REMOVE OLD COMMANDS OK"
