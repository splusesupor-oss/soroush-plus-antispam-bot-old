import os, shutil, re, glob

base=os.getcwd()

print("🔎 scanning splusthon API...")

files=glob.glob("/data/data/com.termux/files/usr/lib/python3.13/site-packages/splusthon/**/*.py", recursive=True)

for f in files:
    try:
        txt=open(f,errors="ignore").read()
        if "ban" in txt.lower() and "participant" in txt.lower():
            print("FOUND:",f)
            for line in txt.splitlines():
                if "ban" in line.lower() and "participant" in line.lower():
                    print(" ",line.strip())
    except:
        pass

print("\n📦 backup...")
for f in ["main.py","modules/admin_actions.py"]:
    if os.path.exists(f):
        shutil.copy2(f,f+".before_auto_ban_fix")
        print("backup:",f)

print("""
مرحله تشخیص تمام شد.
عمداً هنوز کد را تغییر ندادم چون باید نام متد واقعی API سروش مشخص شود.
""")
