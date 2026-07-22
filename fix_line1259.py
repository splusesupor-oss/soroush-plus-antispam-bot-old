from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

out=[]
for i,l in enumerate(lines):
    if i == 1258 and l.strip()=="pass":
        continue
    out.append(l)

p.write_text("\n".join(out),encoding="utf-8")
print("✅ pass خراب حذف شد")
