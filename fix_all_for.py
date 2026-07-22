from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

for i, l in enumerate(lines):
    s = l.strip()

    if s.startswith("for ") and s.endswith(":"):
        base = len(l) - len(l.lstrip())

        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1

        if j < len(lines):
            nxt_indent = len(lines[j]) - len(lines[j].lstrip())

            if nxt_indent <= base:
                lines[j] = " " * (base + 4) + lines[j].lstrip()

p.write_text("\n".join(lines), encoding="utf-8")

print("✅ تمام for ها بررسی شدند")
