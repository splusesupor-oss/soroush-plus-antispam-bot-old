from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

for i in range(min(80, len(lines))):
    print(i+1, repr(lines[i]))
