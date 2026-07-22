#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p=Path("main.py")
s=p.read_text(encoding="utf-8")

if "is_banned" not in s:
    s=s.replace(
        "from modules.banned_storage import add_banned, remove_banned",
        "from modules.banned_storage import add_banned, remove_banned, is_banned"
    )

insert = r'''

        @self.client.on(events.ChatAction())
        async def banned_join_check(event):
            try:
                if not event.user_joined and not event.user_added:
                    return

                user = await event.get_user()
                if not user:
                    return

                chat_id = event.chat_id
                user_id = user.id

                if is_banned(chat_id, user_id):
                    await self.client.kick_participant(
                        chat_id,
                        user
                    )

                    print(
                        f"🚫 blocked banned user rejoin: {user_id}"
                    )

            except Exception as e:
                print(f"join ban check error: {e}")

'''

marker="        @self.client.on(events.NewMessage())"

if marker in s and "banned_join_check" not in s:
    s=s.replace(marker, insert+"\n"+marker)
    p.write_text(s,encoding="utf-8")
    print("join check added")
else:
    print("already added or marker missing")
PY

python3 -m py_compile main.py && echo "syntax ok"
