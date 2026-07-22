#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

block = '''              # RIDDLE_SAFE_INSERTED
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply("🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده")
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return
'''

if block not in s:
    print("❌ riddle block not found")
    exit()

s = s.replace(block, "")

marker = '              clean_text = message_text.strip()'

pos = s.find(marker)

# پیدا کردن دومین clean_text (بعد از جرعت)
pos = s.find(marker, pos + 1)

if pos == -1:
    print("❌ second clean_text not found")
    exit()

insert_pos = pos + len(marker)

s = s[:insert_pos] + "\n\n" + block + s[insert_pos:]

p.write_text(s, encoding="utf-8")

print("✅ riddle moved safely")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
