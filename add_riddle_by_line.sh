#!/bin/bash

cp main.py main.py.before_riddle_line

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
lines = p.read_text(encoding="utf-8").splitlines(True)

if any("RIDDLE_LINE_FIXED" in x for x in lines):
    print("already installed")
    exit()

insert_at = 266  # قبل از خط 267 فونت ساز

code = '''
              # RIDDLE_LINE_FIXED
              if clean_text == "چیستان":
                  try:
                      q = new_riddle(chat_id, user_id)
                      await event.reply(
                          "🧩 چیستان:\\n\\n" + q +
                          "\\n\\n⏳ ۵۰ ثانیه فرصت داری"
                      )
                  except Exception as e:
                      self.logger.log_error(f"خطای چیستان: {e}")
                  return

              answer = get_answer(chat_id, user_id)
              if answer:
                  try:
                      if check_answer(chat_id, user_id, clean_text):
                          await event.reply("✅ پاسخ درست بود")
                          return
                  except Exception as e:
                      self.logger.log_error(f"خطای جواب چیستان: {e}")

'''

lines.insert(insert_at, code)

p.write_text("".join(lines), encoding="utf-8")
print("✅ inserted by line")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
