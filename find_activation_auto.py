from pathlib import Path

keys = [
    "فعال",
    "سازی",
    "فعال‌سازی",
    "activation",
    "activate",
    "OWNER DEBUG",
    "روباه"
]

for p in Path(".").rglob("*.py"):
    try:
        t = p.read_text(encoding="utf-8", errors="ignore")
        if any(k in t for k in keys):
            print("FOUND:", p)
            for i,l in enumerate(t.splitlines(),1):
                if any(k in l for k in keys):
                    print(i, l[:120])
    except:
        pass
