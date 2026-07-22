#!/bin/bash

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''            await self.client.kick_participant(
                chat_id,
                user_entity
            )'''

new='''            from splusthon import functions, types

            chat = await self.client.get_input_entity(chat_id)
            user = await self.client.get_input_entity(user_entity)

            await self.client(
                functions.channels.EditBannedRequest(
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
                        send_polls=True,
                        until_date=None
                    )
                )
            )'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("reply kick permanent fixed")
else:
    print("target not found")
PY

python3 -m py_compile main.py && echo "syntax ok"
