from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

backup = p.with_name("message_handler.py.before_clear_remove_auto")
shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

out=[]

for line in lines:
    if "clear_user(" in line:
        out.append("            # clear_user disabled: keep history for repeat ban")
        continue
    out.append(line)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ clear_user removed")
print("backup:", backup)
