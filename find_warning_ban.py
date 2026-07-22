from pathlib import Path

for f in Path(".").rglob("*.py"):
    try:
        t=f.read_text(encoding="utf-8",errors="ignore")
    except:
        continue

    if "تعداد اخطار" in t or "warning" in t.lower() or "threshold" in t:
        print("\n====",f,"====")
        for i,line in enumerate(t.splitlines(),1):
            if any(x in line for x in ["warning","threshold","punish_user","ban_user","اخطار","4"]):
                print(i, line.strip())
