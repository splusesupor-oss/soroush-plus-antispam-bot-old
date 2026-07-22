from pathlib import Path
import re

patterns = [
    r"ban_user",
    r"EditBannedRequest",
    r"kick_participant",
    r"ChatBannedRights",
    r"is_banned",
    r"add_banned",
    r"remove_banned",
    r"strike",
    r"violation",
    r"penalty",
    r"limit",
    r"5/5",
    r"threshold",
    r"auto.?ban",
    r"ban",
]

root = Path(".")

for p in root.rglob("*.py"):
    if "__pycache__" in str(p):
        continue

    try:
        text = p.read_text(encoding="utf-8")
    except:
        continue

    lines = text.splitlines()

    for i,line in enumerate(lines,1):
        for pat in patterns:
            if re.search(pat,line,re.I):
                print(f"\n📌 {p}:{i}")
                print("   "+line.strip())
                break
