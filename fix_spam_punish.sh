#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''result = await self.admin_actions.punish_user(
                              chat_id,
                              user_id,
                              username
                          )'''

new = '''try:
                              result = await self.admin_actions.punish_user(
                                  chat_id,
                                  user_id,
                                  username
                              )
                          except Exception as e:
                              print("PUNISH ERROR:", repr(e))
                              result = False'''

if old in s:
    s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
    print("✅ punish patch done")
else:
    print("⚠️ target not found")

PY

python3 -m py_compile main.py && echo "✅ syntax ok"
