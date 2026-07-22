from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_suffix(".before_debug_indent_fix")

shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

lines = text.splitlines()

fixed = []
skip = False

for line in lines:
    if line.strip().startswith("print(\"ADMIN DEBUG USER:"):
        skip = True
        continue

    if skip:
        if line.strip().startswith("participant = getattr(user,"):
            fixed.append("                participant = getattr(user, \"participant\", None)")
            skip = False
        continue

    fixed.append(line)

p.write_text("\n".join(fixed) + "\n", encoding="utf-8")

print("✅ indentation fixed")
print("backup:", backup)
