from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if "فعال سازی شد" in l:
        print("LINE:",i+1)
        for x in range(max(0,i-10), min(len(lines),i+15)):
            print(f"{x+1}: {lines[x]}")
        print("------------")
