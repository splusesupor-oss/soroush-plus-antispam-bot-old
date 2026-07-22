#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"

cp main.py main_before_heavy_spam_fix.py

python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''# ریم مستقیم بدون اخطار
                      await self.admin_actions.send_warning(
                          chat_id,
                          user_id,
                          username
                      )'''

new='''# اسپم سنگین چندخطی = حذف و محدودیت فوری
                      try:
                          await self.client.send_message(
                              chat_id,
                              f"⛔️ کاربر @{username or user_id} به دلیل ارسال اسپم سنگین حذف شد."
                          )
                      except:
                          pass

                      try:
                          await self.admin_actions.ban_user(
                              chat_id,
                              user_id
                          )
                      except:
                          pass'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("heavy spam fixed")
else:
    print("target not found")
PY

python3 -m py_compile main.py && echo "syntax ok"
