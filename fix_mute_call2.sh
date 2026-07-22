#!/data/data/com.termux/files/usr/bin/bash

cp main.py main.py.before_mute_fix2

python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

s=s.replace(
"add_mute(chat_id)\n                    result = await self.admin_actions.mute_user(\n                        chat_id,\n                        target_user.id,\n                        0\n                    )",
"result = await self.admin_actions.mute_user(\n                        chat_id,\n                        target_user.id\n                    )"
)

s=s.replace(
"if result:\n                        await event.reply(",
"if result:\n                        add_mute(chat_id)\n                        await event.reply("
)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile main.py && echo "MUTE CALL FIX 2 OK"
