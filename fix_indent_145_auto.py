from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(135,155):
    print(i+1,repr(lines[i]))

# کم کردن indent اضافه در محدوده history
for i in range(140,170):
    if i < len(lines) and lines[i].startswith("            "):
        lines[i]=lines[i][4:]

p.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("✅ indent fixed")
