from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = Path("handlers/message_handler.before_indent_cleanup.py")

shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

fixed = []

for line in lines:
    fixed.append(line.expandtabs(4))

p.write_text("\n".join(fixed) + "\n", encoding="utf-8")

print("✅ tabs converted")
print("backup:", backup)
