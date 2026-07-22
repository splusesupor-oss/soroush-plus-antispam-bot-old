#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("modules/admin_actions.py")
s = p.read_text(encoding="utf-8")

old = '''            # remove user
            await self.client.kick_participant(
                chat_id,
                user
            )
'''

new = '''            # real permanent ban
            from splusthon import types
            from splusthon.tl import functions

            chat = await self.client.get_input_entity(chat_id)
            participant = await self.client.get_input_entity(user)

            await self.client(
                functions.channels.EditBannedRequest(
                    channel=chat,
                    participant=participant,
                    banned_rights=types.ChatBannedRights(
                        view_messages=True,
                        send_messages=True,
                        send_media=True,
                        send_stickers=True,
                        send_gifs=True,
                        send_games=True,
                        send_inline=True,
                        send_polls=True,
                        until_date=None
                    )
                )
            )
'''

if old not in s:
    print("old kick block not found")
else:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("real ban fixed")

PY

python3 -m py_compile modules/admin_actions.py && echo "syntax ok"
