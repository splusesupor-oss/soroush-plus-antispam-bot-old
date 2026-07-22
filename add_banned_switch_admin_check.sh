#!/data/data/com.termux/files/usr/bin/bash

cp main.py main.py.before_banned_switch_admin_check

python3 - <<'PY'
p="main.py"
s=open(p,encoding="utf-8").read()

needle='''        cmd = parts[0].lower()\n\n        try:\n'''

insert='''        cmd = parts[0].lower()\n\n        if text in ["لغو کلمات ممنوعه", "فعال کلمات ممنوعه"]:\n            if not await self.is_admin_user(event, admin_id):\n                await event.respond("❌ فقط مدیر می‌تواند این دستور را اجرا کند")\n                return\n            if text == "لغو کلمات ممنوعه":\n                disable(chat_id)\n                await event.respond("✅ کلمات ممنوعه برای این گروه خاموش شد")\n                return\n            if text == "فعال کلمات ممنوعه":\n                enable(chat_id)\n                await event.respond("✅ کلمات ممنوعه برای این گروه فعال شد")\n                return\n\n        try:\n'''

if needle not in s:
    print("TARGET NOT FOUND")
else:
    s=s.replace(needle,insert,1)

open(p,"w",encoding="utf-8").write(s)
PY

python3 -m py_compile main.py && echo "BANNED SWITCH ADMIN CHECK OK"
