from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(1320,1410):
    lines[i] = lines[i].replace("\t","    ")

# فقط محدوده خراب را با 4 فاصله استاندارد می‌کنیم
for i in range(1338,1410):
    if lines[i].strip():
        lines[i] = "          " + lines[i].lstrip()

p.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("CLEAN DONE")
