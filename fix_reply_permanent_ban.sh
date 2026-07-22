#!/bin/bash

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

s=s.replace(
'''await self.client.kick_participant(
                        chat_id,
                        user_entity
                    )''',
'''from splusthon import types
                    from splusthon.tl import functions

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
)

open(p,"w",encoding="utf-8").write(s)
print("reply permanent ban fixed")
PY

python3 -m py_compile main.py && echo "syntax ok"
