from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip()=="return" and i+1 < len(lines):
        if i==1204:
            lines[i]="            return"

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
