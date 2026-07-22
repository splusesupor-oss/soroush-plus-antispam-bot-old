from pathlib import Path

p=Path("test_main.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip()=="if is_spam:":
        print("پیدا شد خط:", i+1)
        lines[i]="            if is_spam:"
        break
else:
    print("❌ پیدا نشد")
    exit()

p.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("✅ تورفتگی if is_spam اصلاح شد")
