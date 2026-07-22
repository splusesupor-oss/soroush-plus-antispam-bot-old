from pathlib import Path

p = Path("handlers/message_handler.py")
t = p.read_text(encoding="utf-8")

imports = [
    "from modules.riddles import new_riddle",
    "from modules.jorat_haghighat import get_jorat, get_haghighat",
    "from modules.admin_actions import add_mute",
    "from splusthon.tl.types import MessageEntityBold",
]

for i in imports:
    if i not in t:
        t = i + "\n" + t
        print("added:", i)

p.write_text(t, encoding="utf-8")
print("✅ fixed")
