from pathlib import Path
import re

f=Path("handlers/message_handler.py")
t=f.read_text(encoding="utf-8")

cmds=[
"راهنما",
"لیست بازی",
"جستجو ",
"جای خالی",
"چیستان",
"جرعت",
"حقیقت"
]

print("🔎 COMMAND CHECK")

for c in cmds:
    if c in t:
        print("✅ FOUND:",c)
    else:
        print("❌ MISSING:",c)

print("\n🔎 FUNCTION CHECK")

funcs=[
"new_riddle",
"new_fill",
"search_web",
"get_jorat",
"get_haghighat"
]

for x in funcs:
    if x in t:
        print("✅",x)
    else:
        print("❌",x)

print("\n🔎 POSITION CHECK")

for m in re.finditer(r'clean_text\.startswith|clean_text\.strip\(\)',t):
    print(t.count("\n",0,m.start())+1, t[m.start():m.start()+80].replace("\n"," "))

