from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip() == "for w in set(words):":
        base = len(l) - len(l.lstrip())
        
        if i+1 < len(lines):
            lines[i+1] = " " * (base + 4) + lines[i+1].lstrip()

        if i+2 < len(lines):
            lines[i+2] = " " * (base + 8) + lines[i+2].lstrip()

        if i+3 < len(lines):
            lines[i+3] = " " * (base + 8) + lines[i+3].lstrip()

        break

p.write_text("\n".join(lines), encoding="utf-8")
print("✅ حلقه for اصلاح شد")
