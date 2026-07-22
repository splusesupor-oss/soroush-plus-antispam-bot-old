#!/bin/bash

python3 - <<'PY'
from pathlib import Path

# fix logger calls
p = Path("modules/admin_actions.py")
if p.exists():
    s = p.read_text(encoding="utf-8")
    s = s.replace("self.logger.error(", "self.logger.log_error(")
    p.write_text(s, encoding="utf-8")

# fix admin check function
p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = """return is_admin(chat_id, username)"""

new = """return is_admin(chat_id, username)"""

# فقط اطمینان از وجود همین حالت
if old in s:
    s=s.replace(old,new,1)

p.write_text(s, encoding="utf-8")

print("FINAL ADMIN LOGGER FIX OK")
PY

python3 -m py_compile main.py modules/admin_actions.py && echo "COMPILE OK"
