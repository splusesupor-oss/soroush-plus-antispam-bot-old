#!/bin/bash

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''                    await self.client.kick_participant(
                        chat_id,
                        target_user
                    )

                    await event.reply("✅ کاربر اخراج شد")
'''

new='''                    user_entity = await self.client.get_input_entity(target_user)

                    await self.client.kick_participant(
                        chat_id,
                        user_entity
                    )

                    await event.reply("✅ کاربر اخراج شد")
'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("reply kick fixed final")
else:
    print("target not found")
PY

python3 -m py_compile main.py && echo "syntax ok"
