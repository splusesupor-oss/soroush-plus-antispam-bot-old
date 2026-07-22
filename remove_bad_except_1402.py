from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

out=[]

for i,l in enumerate(lines, start=1):
    if i in (1402,1403):
        continue
    out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ removed bad except lines")
