FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    lines=f.readlines()

backup=FILE+".bak_help_last"

with open(backup,"w",encoding="utf-8") as f:
    f.writelines(lines)

out=[]
skip=False

for i,line in enumerate(lines):
    if line.strip() == ")" and i > 0 and "@osine1" in lines[i-1]:
        out.append(line)
        skip=True
        continue

    if skip and line.strip() == "":
        skip=False
        continue

    if skip and "await event.reply(help_text)" in line:
        out.append("                await event.reply(help_text)\n")
        continue

    out.append(line)

with open(FILE,"w",encoding="utf-8") as f:
    f.writelines(out)

print("HELP LAST FIX")
print("BACKUP:",backup)
