from pathlib import Path

p=Path("handlers/message_handler.py")

lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if "فعال سازی" in l or "activate_group" in l:
        print(i+1, repr(l))
