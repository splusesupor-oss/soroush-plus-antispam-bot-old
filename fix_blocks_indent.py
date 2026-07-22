from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

keywords = ("if ", "for ", "while ", "try:")

for i, line in enumerate(lines):
    s = line.strip()

    if s.startswith(keywords) and s.endswith(":"):
        base = len(line) - len(line.lstrip())

        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1

        if j < len(lines):
            nxt = lines[j]
            nxt_indent = len(nxt) - len(nxt.lstrip())

            if nxt_indent <= base:
                lines[j] = " " * (base + 4) + nxt.lstrip()

p.write_text("\n".join(lines), encoding="utf-8")

print("✅ بلوک‌های بدون بدنه اصلاح شدند")
