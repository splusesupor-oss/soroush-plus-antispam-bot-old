from pathlib import Path

for p in Path(".").rglob("*.py"):
    try:
        t=p.read_text(encoding="utf-8")
        if "روباه در گروه" in t or "فعال سازی شد" in t:
            print("\nFOUND:",p)
            for i,l in enumerate(t.splitlines(),1):
                if "فعال سازی شد" in l or "روباه در گروه" in l:
                    print("LINE:",i,l.strip())
    except:
        pass
