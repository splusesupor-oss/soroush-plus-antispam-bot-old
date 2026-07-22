FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    lines=f.readlines()

backup=FILE+".bak_remove_paren"

with open(backup,"w",encoding="utf-8") as f:
    f.writelines(lines)

new=[]

skip=False
for i,line in enumerate(lines, start=1):
    if i == 417 and line.strip() == ")":
        continue
    new.append(line)

with open(FILE,"w",encoding="utf-8") as f:
    f.writelines(new)

print("EXTRA PAREN REMOVED")
print("BACKUP:",backup)
