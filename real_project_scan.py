import os,re

SKIP = {
    "backups",
    "__pycache__",
    ".git",
    "claude_files",
}

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in SKIP]

    for f in files:
        if not f.endswith(".py"):
            continue

        path=os.path.join(root,f)

        if "before_" in path or ".before_" in path or "backup" in path or "broken" in path:
            continue

        txt=open(path,encoding="utf-8",errors="ignore").read()

        print("\n"+path)

        for name,pat in [
            ("iter_participants",r"iter_participants"),
            ("iter_messages",r"iter_messages"),
            ("sleep",r"sleep\("),
            ("json.dump",r"json\.dump"),
            ("json.load",r"json\.load"),
            ("open",r"open\("),
            ("reply",r"\.reply\("),
            ("respond",r"\.respond\("),
            ("delete",r"delete_message|delete_messages"),
            ("edit_permissions",r"edit_permissions"),
        ]:
            c=len(re.findall(pat,txt))
            if c:
                print(f"{name:18} {c}")
