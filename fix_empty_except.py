from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
i = 0

while i < len(lines):
    out.append(lines[i])

    if lines[i].strip().startswith("except Exception as e:"):
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1

        if j >= len(lines) or len(lines[j]) - len(lines[j].lstrip()) <= len(lines[i]) - len(lines[i].lstrip()):
            indent = " " * (len(lines[i]) - len(lines[i].lstrip()) + 4)
            out.append(indent + "pass")

    i += 1

p.write_text("\n".join(out), encoding="utf-8")
print("FIXED EMPTY EXCEPT")
