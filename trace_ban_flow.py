import re

f="main.py"

s=open(f,encoding="utf-8").read()

for x in ["banned_join_check","add_banned(","is_banned(","edit_permissions","kick_participant"]:
    print("\n======",x,"======")
    for m in re.finditer(re.escape(x),s):
        start=max(0,m.start()-120)
        end=min(len(s),m.start()+200)
        print(s[start:end])
        print("-----")
