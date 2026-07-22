import os,ast

ignore=["backup","before","bad","broken","old",".bak"]

for root,dirs,files in os.walk("."):
    for f in files:
        if not f.endswith(".py"):
            continue

        if any(x in f.lower() for x in ignore):
            continue

        p=os.path.join(root,f)

        try:
            ast.parse(open(p,encoding="utf-8").read())
            print("✅",p)
        except Exception as e:
            print("❌",p)
            print("   ",e)
