#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
lines = p.read_text(encoding="utf-8").splitlines(True)

# پیدا کردن اولین خط جرعت با عبارت فارسی
idx = None
for i, line in enumerate(lines):
    if 'get_jorat()' in line:
        idx = i - 1
        break

if idx is None:
    print("❌ get_jorat not found")
    exit()

block = [
'              # RIDDLE_FINAL_CONNECTED\n',
'              if clean_text == "چیستان":\n',
'                  try:\n',
'                      q = new_riddle(chat_id, user_id)\n',
'                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")\n',
'                  except Exception as e:\n',
'                      self.logger.log_error(f"خطای چیستان: {e}")\n',
'                  return\n',
'\n'
]

lines[idx:idx] = block

p.write_text(''.join(lines), encoding="utf-8")

print("✅ inserted before jorat block")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
