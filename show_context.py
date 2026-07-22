from pathlib import Path
lines=Path("handlers/message_handler.py").read_text(encoding="utf-8").splitlines()

for i in range(1318,1338):
    print(f"{i+1}: {repr(lines[i])}")
