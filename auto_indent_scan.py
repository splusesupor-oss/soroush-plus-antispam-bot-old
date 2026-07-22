from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
i = 0

while i < len(lines):
    line = lines[i]
    out.append(line)

    stripped = line.strip()

    # فقط if های ساده که احتمال بدنه خراب دارند
    if stripped.startswith("if ") and stripped.endswith(":"):
        if i + 1 < len(lines):
            nxt = lines[i+1]

            # خط خالی را رد کن
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1

            if j < len(lines):
                current_indent = len(line) - len(line.lstrip())
                next_indent = len(lines[j]) - len(lines[j].lstrip())

                if next_indent <= current_indent:
                    lines[j] = " " * (current_indent + 4) + lines[j].lstrip()

    i += 1

p.write_text("\n".join(lines), encoding="utf-8")

print("✅ اسکن تورفتگی انجام شد")
