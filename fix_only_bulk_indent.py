from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out=[]

for i,l in enumerate(lines, start=1):
    if 1357 <= i <= 1385:
        if l.strip():
            # حذف فاصله اضافه و تنظیم نسبت به if repeat_found
            out.append("                  " + l.lstrip())
        else:
            out.append("")
    else:
        out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")
print("✅ only bulk block indent fixed")
