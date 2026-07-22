from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out=[]
removed=False

for i,l in enumerate(lines):
    if i == 1260 and l.strip().startswith("except Exception as e:"):
        removed=True
        continue
    if removed and i in (1261,1262,1263):
        continue
    out.append(l)

p.write_text("\n".join(out), encoding="utf-8")

print("✅ except اضافی حذف شد")
