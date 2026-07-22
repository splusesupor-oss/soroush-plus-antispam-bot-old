from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

bad = []
for i in range(1320,1450):
    if i < len(lines) and lines[i].strip().startswith("except Exception as e:"):
        bad.append(i)

# حذف except های اضافه داخل محدوده خراب
for i in reversed(bad):
    if i != bad[-1]:
        del lines[i]

# اصلاح فاصله‌های خط‌های محدوده
for i in range(1320, min(1450,len(lines))):
    if lines[i].startswith("                                "):
        lines[i] = lines[i][32:]
        lines[i] = "        " + lines[i].lstrip()

p.write_text("\n".join(lines), encoding="utf-8")
print("FIXED")
