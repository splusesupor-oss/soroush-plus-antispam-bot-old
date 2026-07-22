#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

target = '''              if clean_text in ["جرعت", "جرات", "جرئت"]:'''

if target not in s:
    print("❌ jorat line not found")
    exit()

block = '''              # RIDDLE_FINAL_CONNECTED
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply(
                          "🧩 چیستان:\\n\\n" + q +
                          "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                      )
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

s = s.replace(target, block + target, 1)

p.write_text(s, encoding="utf-8")

print("✅ riddle inserted before jorat")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
