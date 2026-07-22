#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")"

cp main.py main.py.bak
cp modules/admin_storage.py modules/admin_storage.py.bak

python3 - <<'PY'
from pathlib import Path

# اصلاح admin_storage
p = Path("modules/admin_storage.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
'username = username.replace("@", "")',
'username = username.replace("@", "").lower()'
)

s = s.replace(
'return username in data.get(str(group_id), [])',
'return username in [str(x).lower() for x in data.get(str(group_id), [])]'
)

p.write_text(s, encoding="utf-8")


# اصلاح main.py
p = Path("main.py")
s = p.read_text(encoding="utf-8")

# جلوگیری از اسپم گرفتن ادمین
old = '''count = self.tracker.increment(chat_id, user_id)'''

new = '''sender_username = getattr(sender, "username", "") or ""

                # ادمین‌ها اسپم نمی‌گیرند
                if is_admin(chat_id, sender_username):
                    return

                count = self.tracker.increment(chat_id, user_id)'''

s = s.replace(old, new)

p.write_text(s, encoding="utf-8")

print("OK")
PY

echo "✅ اصلاح شد. بکاپ ساخته شد:"
echo "main.py.bak"
echo "modules/admin_storage.py.bak"

