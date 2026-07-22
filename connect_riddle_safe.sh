#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

if "RIDDLE_SAFE_V2" in s:
    print("⚠️ already installed")
    exit()

target = '''              # فونت ساز چند مدلی
'''

insert = '''              # RIDDLE_SAFE_V2
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply(
                          f"🧩 چیستان:\\n\\n{q}\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بدی"
                      )
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

              answer = get_answer(chat_id, user_id)
              if answer:
                  try:
                      if check_answer(chat_id, user_id, clean_text):
                          await event.reply("✅ درست گفتی آفرین")
                          return
                  except Exception as e:
                      self.logger.log_error(f"خطای جواب چیستان: {e}")

'''

if target not in s:
    print("❌ target not found")
    exit(1)

s = s.replace(target, insert + target, 1)

p.write_text(s, encoding="utf-8")
print("✅ riddle connected safe")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
