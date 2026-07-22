from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if "خطای تاریخچه" in l or "history" in l.lower():
        print(i+1, repr(l))
