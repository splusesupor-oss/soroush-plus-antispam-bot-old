#!/data/data/com.termux/files/usr/bin/bash

cp main.py main.py.before_mute_fix

python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

s=s.replace(
"add_mute(chat_id)\n                           result = await self.admin_actions.mute_user(\n",
"result = await self.admin_actions.mute_user(\n")

s=s.replace(
"target_user.id,\n                                                                    0\n",
"target_user.id\n")

old="""if result:
                                      await event.reply(
                                          f"🔇 کاربر {getattr(target_user,'username','کاربر')} سکوت شد"
                                      )"""

new="""if result:
                                      add_mute(chat_id)
                                      await event.reply(
                                          f"🔇 کاربر {getattr(target_user,'username','کاربر')} سکوت شد"
                                      )"""

s=s.replace(old,new)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile main.py && echo "MUTE CALL FIX OK"
