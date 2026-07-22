from pathlib import Path

p=Path("handlers/message_handler.py")

lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip()=="# بررسی تکرار شدید داخل یک پیام":
        lines[i]="        # بررسی تکرار شدید داخل یک پیام"
    if l.strip()=="try:" and i>1335 and i<1345:
        lines[i]="        try:"

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ heavy try level fixed")
