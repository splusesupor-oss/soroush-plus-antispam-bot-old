import os,re

patterns={
"sleep":r"sleep\(",
"requests":r"requests\.",
"aiohttp":r"aiohttp",
"http":r"http",
"json.dump":r"json\.dump",
"json.load":r"json\.load",
"open":r"open\(",
"iter_participants":r"iter_participants",
"iter_messages":r"iter_messages",
"reply":r"\.reply\(",
"respond":r"\.respond\(",
"delete":r"delete_message|delete_messages",
"edit_permissions":r"edit_permissions",
"sqlite":r"sqlite3",
}

for root,_,files in os.walk("."):
    for f in files:
        if not f.endswith(".py"):
            continue
        path=os.path.join(root,f)
        txt=open(path,"r",encoding="utf-8",errors="ignore").read()
        for name,pat in patterns.items():
            c=len(re.findall(pat,txt))
            if c:
                print(f"{path} | {name} | {c}")
