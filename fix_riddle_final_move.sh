#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find('if clean_text == "چیستان":')

if start == -1:
    print("❌ chiestan block not found")
    exit()

# شروع واقعی با فاصله‌های قبل از if
start = s.rfind("\n", 0, start) + 1

end = s.find("                  return", start)

if end == -1:
    print("❌ chiestan return not found")
    exit()

end += len("                  return")

block = s[start:end]

# حذف بخش فعلی
s = s[:start] + s[end:]

# پیدا کردن پایان فیلتر گروه
marker = '                  return\n\n              except Exception as e:'

pos = s.find(marker)

if pos == -1:
    # روش دوم
    marker = '                  return\n\n\n              except Exception as e:'
    pos = s.find(marker)

if pos == -1:
    print("❌ filter position not found")
    exit()

insert = pos + len(marker)

s = s[:insert] + "\n\n" + block.rstrip() + "\n" + s[insert:]

p.write_text(s, encoding="utf-8")

print("✅ riddle moved final")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
