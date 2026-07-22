from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(1325,1340):
    print(i+1,repr(lines[i]))

