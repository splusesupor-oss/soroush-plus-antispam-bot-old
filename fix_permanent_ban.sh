#!/bin/bash

python3 - <<'PY'
p="modules/admin_actions.py"

s=open(p,encoding="utf-8").read()

old='''            await self.client.kick_participant(chat, user)

            self.logger.log_action(
                "BAN/KICK",
                user_id,
                chat_id,
                "حذف دائمی به دلیل اسپم"
            )
'''

new='''            from telethon.tl.functions.channels import EditBannedRequest
            from telethon.tl.types import ChatBannedRights

            rights = ChatBannedRights(
                until_date=None,
                view_messages=True,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True
            )

            await self.client(EditBannedRequest(
                chat,
                user,
                rights
            ))

            self.logger.log_action(
                "BAN",
                user_id,
                chat_id,
                "بن دائمی به دلیل اسپم"
            )
'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("permanent ban fixed")
else:
    print("target not found")
PY

python3 -m py_compile modules/admin_actions.py && echo "syntax ok"
