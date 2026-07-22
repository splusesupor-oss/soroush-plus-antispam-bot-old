#!/bin/bash
cd "$(dirname "$0")"

cp main.py main_before_repeat_heavy_fix.py

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''if repeat_found:
                      from modules.user_map import save_user

                      save_user(chat_id, username, user_id)
                      count = self.tracker.increment(chat_id, user_id)
                      await self.admin_actions.delete_message(chat_id, event=event)

                      await self.admin_actions.send_warning(
                          chat_id=chat_id,
                          username=username,
                          reason="تکرار بیش از حد داخل یک پیام",
                          count=count,
                          threshold=self.config_manager.get("spam_threshold", 3),
                          reply_to=None
                      )'''

new='''if repeat_found:
                      from modules.user_map import save_user

                      save_user(chat_id, username, user_id)

                      # پیام های بسیار سنگین و تکراری = اسپم فوری
                      repeat_count = max(
                          [words.count(w) for w in set(words)]
                      )

                      await self.admin_actions.delete_message(
                          chat_id,
                          event=event
                      )

                      if repeat_count >= 30:
                          try:
                              await self.admin_actions.punish_user(
                                  chat_id,
                                  user_id,
                                  username
                              )
                          except:
                              pass

                          return

                      count = self.tracker.increment(
                          chat_id,
                          user_id
                      )

                      await self.admin_actions.send_warning(
                          chat_id=chat_id,
                          username=username,
                          reason="تکرار بیش از حد داخل یک پیام",
                          count=count,
                          threshold=self.config_manager.get("spam_threshold", 3),
                          reply_to=None
                      )'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("repeat heavy spam fixed")
else:
    print("target not found")

PY

python3 -m py_compile main.py && echo "syntax ok"
