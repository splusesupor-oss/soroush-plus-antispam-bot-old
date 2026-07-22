#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''words = re.findall(r"\\\\w+|[آ-ی]+", message_text.lower())
                  repeat_found = False

                  for w in set(words):
                      if len(w) >= 3 and words.count(w) >= 8:
                          repeat_found = True
                          break

                  if repeat_found:
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
                      )
'''

new='''lines = [
                      x.strip()
                      for x in message_text.splitlines()
                      if x.strip()
                  ]

                  heavy_repeat = False

                  if len(lines) >= 15:
                      unique = set(lines)
                      for line in unique:
                          if lines.count(line) >= 10:
                              heavy_repeat = True
                              break

                  if heavy_repeat:
                      from modules.user_map import save_user

                      save_user(chat_id, username, user_id)

                      await self.admin_actions.delete_message(
                          chat_id,
                          event=event
                      )

                      await self.admin_actions.ban_user(
                          chat_id,
                          user_id
                      )

                      return

                  words = re.findall(r"\\\\w+|[آ-ی]+", message_text.lower())

                  repeat_found = False

                  for w in set(words):
                      if len(w) >= 3 and words.count(w) >= 8:
                          repeat_found = True
                          break

                  if repeat_found:
                      from modules.user_map import save_user

                      save_user(chat_id, username, user_id)

                      count = min(
                          self.tracker.increment(chat_id,user_id),
                          5
                      )

                      await self.admin_actions.delete_message(
                          chat_id,
                          event=event
                      )

                      await self.admin_actions.send_warning(
                          chat_id=chat_id,
                          username=username,
                          reason="تکرار بیش از حد داخل یک پیام",
                          count=count,
                          threshold=5,
                          reply_to=None
                      )
'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("spam logic fixed")
else:
    print("target not found")

PY

python3 -m py_compile main.py && echo "syntax ok"
