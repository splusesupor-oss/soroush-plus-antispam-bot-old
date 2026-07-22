from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

for i in range(145,170):
    if i <= len(lines):
        print(i, repr(lines[i-1]))
