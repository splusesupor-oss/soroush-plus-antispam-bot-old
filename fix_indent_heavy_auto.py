from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

out=[]
i=0

while i < len(lines):
    line=lines[i]

    # حذف guard خراب شده
    if "if getattr(bot, '_already_banned'" in line:
        i += 3
        continue

    out.append(line)
    i+=1

p.write_text("\n".join(out)+"\n",encoding="utf-8")
print("✅ broken guard removed")
