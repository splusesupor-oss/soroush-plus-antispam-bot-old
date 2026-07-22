import ast,os

need=["add_kick","add_mute","add_message"]

for f in os.listdir("modules"):
    if f.endswith(".py"):
        p="modules/"+f
        txt=open(p,encoding="utf8").read()
        for x in need:
            if "def "+x in txt:
                print("FOUND",x,"in",p)
