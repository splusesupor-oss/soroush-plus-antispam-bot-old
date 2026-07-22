import os,re

print("🔎 بررسی سیستم بن\n")

for root,dirs,files in os.walk("."):
    for f in files:
        if f.endswith(".py"):
            path=os.path.join(root,f)
            try:
                s=open(path,encoding="utf-8").read()
            except:
                continue

            if "def add_banned" in s or "def is_banned" in s:
                print("\n📌 فایل:",path)

                for name in ["def add_banned","def is_banned","def remove_banned"]:
                    p=s.find(name)
                    if p!=-1:
                        print("\n---",name,"---")
                        print(s[p:p+800])

print("\n✅ تمام")
