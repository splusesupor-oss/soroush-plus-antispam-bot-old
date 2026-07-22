#!/data/data/com.termux/files/usr/bin/bash

cp main.py main_before_kick_fix.py

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text()

old = '''add_kick(chat_id)
                    await self.client.kick_participant(
                        chat_id,
                        target_user
                    )'''

new = '''add_kick(chat_id)
                    await self.client.kick_participant(
                        chat_id,
                        target_user
                    )

                    try:
                        remove_banned(
                            chat_id,
                            getattr(target_user, "username", "")
                        )
                    except Exception:
                        pass'''

if old in s:
    s = s.replace(old,new)
    p.write_text(s)
    print("fixed kick permanent ban")
else:
    print("target not found")
PY

python3 -m py_compile main.py && echo "syntax ok"
