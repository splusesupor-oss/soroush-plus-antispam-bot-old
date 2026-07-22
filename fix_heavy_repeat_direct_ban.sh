#!/bin/bash

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''                    count = self.tracker.increment(chat_id, user_id)

                    await self.admin_actions.delete_message(chat_id, event=event)

                    await self.admin_actions.send_warning(
                        chat_id=chat_id,
                        username=username,
                        reason="تکرار بیش از حد داخل یک پیام",
                        count=count,
                        threshold=self.config_manager.get("spam_threshold", 3),
                        reply_to=None
                    )

                    if self.tracker.should_punish(chat_id, user_id):
                        punish_key = f"{chat_id}:{user_id}"

                        if punish_key not in self.punished_users:
                            self.punished_users.add(punish_key)

                            await self.admin_actions.punish_user(
                                chat_id,
                                user_id,
                                username
                            )
'''

new='''                    await self.admin_actions.delete_message(
                        chat_id,
                        event=event
                    )

                    print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                    punish_key = f"{chat_id}:{user_id}"

                    if punish_key not in self.punished_users:
                        self.punished_users.add(punish_key)

                        await self.admin_actions.punish_user(
                            chat_id,
                            user_id,
                            username
                        )
'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("heavy repeat direct ban fixed")
else:
    print("target not found")

PY

python3 -m py_compile main.py && echo "syntax ok"
