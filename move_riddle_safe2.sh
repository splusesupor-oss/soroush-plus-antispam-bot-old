#!/bin/bash

cp main.py main.py.before_riddle_move2

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find("              # RIDDLE_SAFE_INSERTED")

if start == -1:
    print("❌ start not found")
    exit()

end = s.find("                  return", start)

if end == -1:
    print("❌ end not found")
    exit()

end = end + len("                  return")

block = s[start:end]

s = s[:start] + s[end:]

marker = "              clean_text = message_text.strip()"

# پیدا کردن دومین clean_text
first = s.find(marker)
second = s.find(marker, first + 1)

if second == -1:
    print("❌ target clean_text not found")
    exit()

pos = second + len(marker)

s = s[:pos] + "\n\n" + block + s[pos:]

p.write_text(s, encoding="utf-8")

print("✅ riddle moved")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
