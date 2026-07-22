from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_activation_logic_fix.py")

shutil.copy(p,backup)

lines=p.read_text(encoding="utf-8").splitlines()

out=[]
i=0

while i < len(lines):
    line=lines[i]

    if "deactivate_group(gid, title)" in line and i>0:
        out.append("                else:")
        out.append(line)
        i+=1
        continue

    out.append(line)
    i+=1

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ fixed activation logic")
print("backup:",backup)
