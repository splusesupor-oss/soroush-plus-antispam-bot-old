#!/data/data/com.termux/files/usr/bin/bash

python3 <<'PY'
from pathlib import Path

p = Path("modules/admin_actions.py")
s = p.read_text(encoding="utf-8")

old = '''await self.client.kick_participant(
                chat_id,
                user
            )'''

new = '''from telethon import functions, types

            chat = await self.client.get_input_entity(chat_id)

            await self.client(functions.channels.EditBannedRequest(
                channel=chat,
                participant=user,
                banned_rights=types.ChatBannedRights(
                    view_messages=True,
                    send_messages=True,
                    send_media=True,
                    send_stickers=True,
                    send_gifs=True,
                    send_games=True,
                    send_inline=True,
                    send_polls=True
                )
            ))'''

if old in s:
    s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
    print("permanent ban replaced")
else:
    print("target not found")

PY

python3 -m py_compile modules/admin_actions.py && echo "syntax ok"
