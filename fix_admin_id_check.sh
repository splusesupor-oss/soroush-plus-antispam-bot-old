#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p=Path("main.py")
s=p.read_text(encoding="utf-8")

old='''username = getattr(sender, "username", None)

            chat = await event.get_chat()
            chat_id = getattr(chat, "id", None)

            return is_admin(chat_id, username)'''

new='''username = getattr(sender, "username", None)

            chat = await event.get_chat()
            chat_id = getattr(chat, "id", None)

            if is_admin(chat_id, username):
                return True

            # بررسی مالک یا ادمین با آیدی عددی
            if str(user_id) == "68074059":
                return True

            return False'''

if old not in s:
    print("TARGET NOT FOUND")
else:
    s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("ADMIN ID CHECK FIX OK")
PY

python3 -m py_compile main.py && echo "MAIN OK"
