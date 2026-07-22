import os,re

commands = [
    "فونت",
    "جرعت",
    "حقیقت",
    "سکوت",
    "رفع سکوت",
    "آمار گروه",
    "ریست آمار",
    "اخراج",
    "راهنما",
    "چیستان"
]

print("=== COMMAND CHECK ===")

for cmd in commands:
    found=[]
    for root,dirs,files in os.walk("."):
        for f in files:
            if f.endswith(".py"):
                p=os.path.join(root,f)
                try:
                    data=open(p,encoding="utf8").read()
                    if cmd in data:
                        found.append(p)
                except:
                    pass

    print("\n",cmd)
    if found:
        for x in found[:5]:
            print(" OK:",x)
    else:
        print(" NOT FOUND")


print("\n=== IMPORT CHECK ===")

need=[
"MessageEntityBold",
"new_riddle",
"get_answer",
"add_kick",
"add_mute",
"add_message"
]

for n in need:
    ok=False
    for root,dirs,files in os.walk("."):
        for f in files:
            if f.endswith(".py"):
                p=os.path.join(root,f)
                try:
                    d=open(p,encoding="utf8").read()
                    if n in d:
                        print(n,"=>",p)
                        ok=True
                        break
                except:
                    pass
    if not ok:
        print(n,"MISSING")
