#!/data/data/com.termux/files/usr/bin/bash

cp main.py main_before_fix_now.py

python3 - <<'PY'
from pathlib import Path

p=Path("main.py")
s=p.read_text()

# جلوگیری از ثبت اخراج به عنوان بن دائمی
s=s.replace(
'''add_kick(chat_id)
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
                        pass''',
'''add_kick(chat_id)
                    await self.client.kick_participant(
                        chat_id,
                        target_user
                    )'''
)

p.write_text(s)
print("kick fixed")
PY

python3 -m py_compile main.py && echo "syntax ok"
