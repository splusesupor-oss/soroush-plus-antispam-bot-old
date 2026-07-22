#!/bin/bash
python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''                      target_user = await reply_msg.get_sender()
'''

new = '''                      if not reply_msg:
                          await event.reply("❌ پیام ریپلای شده پیدا نشد")
                          return

                      target_user = await reply_msg.get_sender()
'''

if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ مشکل اخراج اصلاح شد")
else:
    print("❌ خط پیدا نشد")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
