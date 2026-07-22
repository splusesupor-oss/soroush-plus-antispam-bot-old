#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p=Path("modules/banned_storage.py")
s=p.read_text()

if "def is_banned" not in s:
    s += '''

def is_banned(group_id, user_id):
    data = load_banned()
    gid = str(group_id)

    if gid not in data:
        return False

    uid = str(user_id)

    return uid in [str(x) for x in data[gid]]
'''
    p.write_text(s)

print("storage fixed")
PY

python3 -m py_compile modules/banned_storage.py && echo "syntax ok"
