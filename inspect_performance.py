from pathlib import Path
import re

ROOT = Path(".")

patterns = {
    "iter_participants": r"iter_participants",
    "sleep": r"asyncio\.sleep|sleep\(",
    "http": r"aiohttp|requests|get\(|post\(",
    "json_dump": r"json\.dump|json\.dumps",
    "json_load": r"json\.load|json\.loads",
    "open_file": r"\bopen\(",
    "await": r"\bawait\b",
    "reply": r"\.reply\(",
    "respond": r"\.respond\(",
    "edit_permissions": r"edit_permissions",
    "delete_messages": r"delete_messages",
    "delete_message": r"delete_message",
    "logger": r"logger",
    "history": r"is_repeat|save_history|history",
    "stats": r"group_stats|save_stats|add_deleted",
    "regex": r"re\.search|re\.match|re\.findall|re\.compile",
}

total = {k:0 for k in patterns}

for f in ROOT.rglob("*.py"):
    if "__pycache__" in str(f):
        continue
    try:
        txt = f.read_text(encoding="utf-8",errors="ignore")
    except:
        continue

    hit=False
    for name,pat in patterns.items():
        m=list(re.finditer(pat,txt))
        if m:
            if not hit:
                print("\n"+"="*70)
                print(f)
                print("="*70)
                hit=True
            total[name]+=len(m)
            for x in m[:20]:
                line=txt.count("\n",0,x.start())+1
                print(f"{line:5} | {name}")

print("\n")
print("="*70)
print("TOTAL")
print("="*70)

for k,v in sorted(total.items(),key=lambda x:x[1],reverse=True):
    print(f"{k:20} {v}")

print("\n")
print("="*70)
print("LARGE FILES")
print("="*70)

sizes=[]
for f in ROOT.rglob("*.py"):
    try:
        lines=sum(1 for _ in open(f,encoding="utf-8",errors="ignore"))
        sizes.append((lines,f))
    except:
        pass

for l,f in sorted(sizes,reverse=True)[:20]:
    print(f"{l:5} {f}")

print("\n")
print("="*70)
print("HANDLE_NEW_MESSAGE SIZE")
print("="*70)

for f in ROOT.rglob("*.py"):
    try:
        txt=f.read_text(encoding="utf-8",errors="ignore")
    except:
        continue
    if "async def handle_new_message" in txt:
        lines=txt.splitlines()
        start=None
        for i,l in enumerate(lines):
            if "async def handle_new_message" in l:
                start=i
                break
        if start is not None:
            end=len(lines)
            for j in range(start+1,len(lines)):
                if lines[j].startswith("async def "):
                    end=j
                    break
            print(f"{f}")
            print("Lines:",end-start)

