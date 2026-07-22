from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
fix = False

for i, line in enumerate(lines):
    if "# اخطار کاربر با ریپلای" in line:
        out.append("# اخطار کاربر با ریپلای")
        fix = True
        continue

    if fix and line.strip().startswith("if clean_text == \"اخطار\":"):
        out.append("    if clean_text == \"اخطار\":")
        continue

    if fix:
        # فقط بخش اخطار را یک سطح کم می‌کنیم
        if line.startswith("        "):
            out.append(line[4:])
        else:
            out.append(line)
    else:
        out.append(line)

p.write_text("\n".join(out), encoding="utf-8")
print("✅ تورفتگی بخش اخطار تنظیم شد")
