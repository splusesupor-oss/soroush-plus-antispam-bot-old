from pathlib import Path

p = Path("handlers/message_handler.py")
t = p.read_text(encoding="utf-8")

imports = [
    "import asyncio",
    "from modules.jorat_haghighat import get_jorat, get_haghighat",
    "from modules.riddles import new_riddle",
]

add = []
for i in imports:
    if i not in t:
        add.append(i)

if add:
    t = "\n".join(add) + "\n" + t
    p.write_text(t, encoding="utf-8")
    print("✅ Missing imports restored:")
    for x in add:
        print(x)
else:
    print("✅ Imports already exist")

