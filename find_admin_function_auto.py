from pathlib import Path

for p in Path(".").rglob("*.py"):
    try:
        t=p.read_text(encoding="utf-8")
        if "get_activation_admin_info" in t:
            print("FOUND:", p)
            for i,l in enumerate(t.splitlines(),1):
                if "get_activation_admin_info" in l:
                    print("LINE:", i, l)
    except:
        pass
