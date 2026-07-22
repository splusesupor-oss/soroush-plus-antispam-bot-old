#!/bin/bash

cp main.py main.py.before_riddle_position_fix

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find("              # RIDDLE_SAFE_INSERTED")
if start == -1:
    print("❌ riddle marker not found")
    exit()

end = s.find("                  return", start)
if end == -1:
    print("❌ riddle return not found")
    exit()

end += len("                  return")

block = s[start:end]

# حذف بخش فعلی
s = s[:start] + s[end:]

# قرار دادن بعد از except فیلتر گروه
target = '''              except Exception as e:
                  self.logger.log_error(
                      f"خطای فیلتر گروه: {e}"
                  )
'''

pos = s.find(target)

if pos == -1:
    print("❌ filter block not found")
    exit()

insert_pos = pos + len(target)

s = s[:insert_pos] + "\n\n" + block + s[insert_pos:]

p.write_text(s, encoding="utf-8")

print("✅ riddle moved after chat_id/user_id")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
