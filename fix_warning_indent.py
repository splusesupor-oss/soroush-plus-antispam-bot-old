from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

start = None
end = None

for i,l in enumerate(lines):
    if "# اخطار کاربر با ریپلای" in l:
        start = i
    if start is not None and "# سکوت کاربر با ریپلای" in l:
        end = i
        break

if start is None or end is None:
    print("❌ پیدا نشد")
    raise SystemExit

# پیدا کردن تورفتگی بخش قبل
new_lines = []

for i,l in enumerate(lines):
    if start <= i < end:
        if l.strip():
            new_lines.append("    " + l)
        else:
            new_lines.append(l)
    else:
        new_lines.append(l)

p.write_text("\n".join(new_lines), encoding="utf-8")

print("✅ تورفتگی اصلاح شد")
