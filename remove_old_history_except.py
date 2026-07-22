from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

backup=Path("handlers/message_handler.before_remove_old_except")
backup.write_text("\n".join(lines)+"\n",encoding="utf-8")

out=[]
skip=False

for i,l in enumerate(lines):
    if i+1 == 189 and "except Exception as e:" in l:
        skip=True
        continue

    if skip:
        if "pass" in l:
            skip=False
        continue

    out.append(l)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ old except removed")
print("backup:",backup)
