#!/bin/bash

cp main.py main.py.before_riddle_add_final

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

marker = '''              # بازی جرعت حقیقت'''

if marker not in s:
    print("❌ marker not found")
    exit()

code = '''              # RIDDLE_FINAL_CONNECTED
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

s = s.replace(marker, code + marker, 1)

p.write_text(s, encoding="utf-8")

print("✅ riddle added safely")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
