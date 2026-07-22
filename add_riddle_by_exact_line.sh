#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
lines = p.read_text(encoding="utf-8").splitlines()

if any("RIDDLE_OK_CONNECTED" in x for x in lines):
    print("already exists")
    exit()

insert = [
'              # RIDDLE_OK_CONNECTED',
'              if clean_text == "چیستان":',
'                  try:',
'                      q = new_riddle(chat_id, user_id)',
'                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری")',
'                  except Exception as e:',
'                      self.logger.log_error(f"خطای چیستان: {e}")',
'                  return',
'',
'              if get_answer(chat_id, user_id):',
'                  if check_answer(chat_id, user_id, clean_text):',
'                      await event.reply("✅ پاسخ درست بود")',
'                      return',
'',
]

# پیدا کردن اولین خط فونت با contains
for i,l in enumerate(lines):
    if "startswith" in l and "فونت" in l:
        lines[i:i] = insert
        p.write_text("\n".join(lines)+"\n", encoding="utf-8")
        print("✅ inserted at line", i+1)
        break
else:
    print("❌ font line not found")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
