#!/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find('              if clean_text == "چیستان":')

if start == -1:
    print("❌ chiestan if not found")
    exit()

# پیدا کردن return بعد از بخش چیستان
end = s.find("                  return", start)

if end == -1:
    print("❌ riddle return not found")
    exit()

end += len("                  return")

block_start = s.rfind("\n", 0, start) + 1
block = s[block_start:end]

# حذف بخش فعلی
s = s[:block_start] + s[end:]

# پیدا کردن بخش جرعت/حقیقت بعدی
marker = '              if clean_text in ["حقیقت", "حقیقت بگو"]:'

pos = s.find(marker)

if pos == -1:
    print("❌ truth marker not found")
    exit()

# بعد از return حقیقت قرار بده
insert = s.find("                  return", pos)

if insert == -1:
    print("❌ truth return not found")
    exit()

insert += len("                  return")

s = s[:insert] + "\n\n" + block.rstrip() + "\n" + s[insert:]

p.write_text(s, encoding="utf-8")

print("✅ riddle moved by if")
PY

python3 -m py_compile main.py && echo "✅ syntax ok"
