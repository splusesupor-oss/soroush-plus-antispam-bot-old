#!/bin/bash

cp main.py main.py.before_riddle_safe_final

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

if "RIDDLE_SAFE_INSERTED" in s:
    print("⚠️ riddle already exists")
    exit()

target = '''              clean_text = message_text.strip()

'''

insert = '''              clean_text = message_text.strip()

              # RIDDLE_SAFE_INSERTED
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply(
                          "🧩 چیستان:\\n\\n" + q + "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بده"
                      )
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

'''

if target not in s:
    print("❌ target not found")
    exit()

s = s.replace(target, insert, 1)

p.write_text(s, encoding="utf-8")
print("✅ riddle inserted safely")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
