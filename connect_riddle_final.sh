#!/bin/bash

cp main.py main.py.before_riddle_final

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

if "RIDDLE_FINAL_CONNECTED" in s:
    print("already installed")
    exit()

marker = '''              # فونت ساز چند مدلی
'''

insert = '''
              # RIDDLE_FINAL_CONNECTED
              clean_text = message_text.strip()

              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply(
                          "🧩 چیستان:\\n\\n"
                          + q +
                          "\\n\\n⏳ ۵۰ ثانیه فرصت داری جواب بدی"
                      )
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

              answer = get_answer(chat_id, user_id)
              if answer:
                  try:
                      if check_answer(chat_id, user_id, clean_text):
                          await event.reply("✅ آفرین! پاسخ درست بود")
                          return
                  except Exception as e:
                      self.logger.log_error(f"خطای جواب چیستان: {e}")

'''

if marker not in s:
    print("marker not found")
    exit()

s = s.replace(marker, insert + marker, 1)

p.write_text(s, encoding="utf-8")
print("✅ riddle final connected")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"

