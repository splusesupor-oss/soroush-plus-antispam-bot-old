from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_name("message_handler.before_structure_fix.py")

shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

out = []
found_admin = False

for line in lines:
    if line.startswith("    async def handle_admin_commands"):
        found_admin = True
        out.append("async def handle_admin_commands(self, event, text: str, admin_id: int, chat_id: int):")
        continue

    if found_admin:
        if line.startswith("        ") or line.strip()=="":
            out.append(line)
        else:
            found_admin=False
            out.append(line)
        continue

    out.append(line)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ structure fixed")
print("backup:", backup)
