from pathlib import Path

lines=Path("handlers/message_handler.py").read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if "try:" in l or "except" in l or "finally" in l:
        if 350 <= i <= 470:
            print(i+1, repr(l))
