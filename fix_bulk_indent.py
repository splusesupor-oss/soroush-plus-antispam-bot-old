from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out=[]
fix=False

for i,l in enumerate(lines):
    if "bulk delete 100x" in l:
        fix=True

    if fix and 1350 <= i+1 <= 1390:
        if l.strip():
            out.append("                " + l.lstrip())
        else:
            out.append("")
    else:
        out.append(l)

p.write_text("\n".join(out)+"\n",encoding="utf-8")
print("✅ indent fixed")
