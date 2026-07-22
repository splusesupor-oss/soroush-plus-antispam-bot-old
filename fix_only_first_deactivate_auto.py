from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_only_first_deactivate_fix.py")

shutil.copy(p,backup)

lines=p.read_text(encoding="utf-8").splitlines()

start=None
for i,l in enumerate(lines):
    if 'if clean_text in ["فعال سازی", "غیر فعال"]' in l:
        start=i
        break

if start is None:
    print("not found")
    exit()

for i in range(start, start+60):
    if "deactivate_group(gid, title)" in lines[i]:
        lines[i] = "                else:\n                " + lines[i]
        break

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("fixed")
print(backup)
