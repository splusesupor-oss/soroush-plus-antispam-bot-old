import os,re,ast,subprocess

FILE="handlers/message_handler.py"

print("🔎 SCAN START")

text=open(FILE,encoding="utf-8").read()

# پیدا کردن import های لازم از کل پروژه
functions={}

for root,_,files in os.walk("."):
    for f in files:
        if f.endswith(".py"):
            p=os.path.join(root,f)
            try:
                t=open(p,encoding="utf-8").read()
                for x in re.findall(r"(?:def|async def)\s+([a-zA-Z_]\w*)",t):
                    functions.setdefault(x,p)
            except:
                pass

tree=ast.parse(text)

defined=set()
imports=set()
calls=set()

for n in ast.walk(tree):
    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
        defined.add(n.name)

    if isinstance(n,ast.ImportFrom):
        for i in n.names:
            imports.add(i.name)

    if isinstance(n,ast.Call):
        if isinstance(n.func,ast.Name):
            calls.add(n.func.id)


missing=[]

for c in calls:
    if c not in defined and c not in imports:
        if c in functions:
            missing.append((c,functions[c]))

print("❌ MISSING IMPORTS")

for x,p in missing:
    print(x,"=>",p)

# اضافه کردن import ها
add=[]

for x,p in missing:
    if "modules/" in p:
        mod=p.replace("./","").replace("/",".")

        if mod.endswith(".py"):
            mod=mod[:-3]

        line=f"from {mod} import {x}"

        if line not in text:
            add.append(line)


if add:
    text="\n".join(add)+"\n"+text

    open(FILE,"w",encoding="utf-8").write(text)

    print("✅ IMPORTS FIXED")

else:
    print("✅ NO IMPORT FIX")


# تست کامپایل
r=subprocess.run(
["python3","-m","py_compile",FILE],
capture_output=True,text=True
)

if r.returncode==0:
    print("✅ COMPILE OK")
else:
    print("❌ COMPILE ERROR")
    print(r.stderr)

