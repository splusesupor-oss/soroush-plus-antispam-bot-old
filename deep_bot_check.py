import os,ast,importlib.util,sys

print("🧠 Deep Bot Check\n")

pyfiles=[]
for root,dirs,files in os.walk("."):
    if "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            pyfiles.append(os.path.join(root,f))

syntax_bad=[]

for f in pyfiles:
    try:
        ast.parse(open(f,encoding="utf-8").read())
    except Exception as e:
        syntax_bad.append((f,str(e)))

print("========== SYNTAX ==========")

if syntax_bad:
    for x in syntax_bad:
        print("❌",x[0],"\n ",x[1])
else:
    print("✅ همه فایل‌های پایتون سالم هستند")


print("\n========== MAIN CHECK ==========")

if os.path.exists("main.py"):
    s=open("main.py",encoding="utf-8").read()

    for x in [
        "add_banned",
        "remove_banned",
        "is_banned",
        "edit_permissions",
        "kick_participant",
        "banned_join_check"
    ]:
        print(
            ("✅ " if x in s else "❌ "),
            x
        )

    print("\nتعداد:")
    for x in ["add_banned(","remove_banned(","is_banned(","edit_permissions(","kick_participant("]:
        print(x, s.count(x))


print("\n========== STORAGE TEST ==========")

try:
    from modules.banned_storage import *

    print("✅ storage import شد")

    print("is_banned test:",
          is_banned(22770700,68893049,""))

except Exception as e:
    print("❌ storage خراب:",e)


print("\n========== BAD CALL CHECK ==========")

for f in pyfiles:
    try:
        s=open(f,encoding="utf-8").read()

        if "remove_banned(chat_id, username)" in s:
            print("⚠️ username remove:",f)

        if "kick_participant" in s and "main.py" in f:
            print("⚠️ kick هنوز در main:",f)

    except:
        pass


print("\n========== DUPLICATE FUNCTION ==========")

for f in pyfiles:
    try:
        tree=ast.parse(open(f,encoding="utf-8").read())

        funcs={}

        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef):
                funcs[n.name]=funcs.get(n.name,0)+1

        for k,v in funcs.items():
            if v>1:
                print("⚠️",f,k,"تعداد:",v)

    except:
        pass


print("\n🏁 تمام شد")
