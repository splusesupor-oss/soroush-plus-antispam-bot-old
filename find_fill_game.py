from pathlib import Path
import re

files = [
    "handlers/message_handler.py",
    "modules/group_stats.py",
    "modules/game.py",
    "main.py"
]

keys = [
    "امتیاز",
    "score",
    "جای خالی",
    "جای‌خالی",
    "خالی",
    "جواب",
    "answer",
    "correct",
    "30",
    "ثانیه",
    "timer",
    "game"
]

for f in files:
    p=Path(f)
    if not p.exists():
        continue

    print("\n==========", f, "==========")

    text=p.read_text(encoding="utf-8", errors="ignore").splitlines()

    for i,line in enumerate(text,1):
        if any(k.lower() in line.lower() for k in keys):
            print(f"{i}: {line.strip()}")
