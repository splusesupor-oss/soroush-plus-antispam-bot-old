from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_name("message_handler.before_indent_cleanup2.py")

shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

fixed = []
for line in lines:
    line = line.replace("\t", "    ")
    
    if line.startswith("        async def ") and "handle_" in line:
        line = line[8:]

    if line.startswith("    async def ") and line.strip().startswith("async def"):
        line = line.strip()

    fixed.append(line.rstrip())

p.write_text("\n".join(fixed)+"\n", encoding="utf-8")

print("✅ indentation cleanup done")
print("backup:", backup)
