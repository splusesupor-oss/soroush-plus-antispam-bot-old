from pathlib import Path
import re

files = sorted(Path(".").glob("main.py*"))

print("🔎 در حال بررسی بکاپ‌ها...\n")

found = []

for f in files:
    try:
        s = f.read_text(encoding="utf-8", errors="ignore")

        score = 0
        tags = []

        if "add_banned" in s:
            score += 2
            tags.append("add_banned")

        if "is_banned" in s:
            score += 2
            tags.append("is_banned")

        if "ChatAction" in s:
            score += 2
            tags.append("ChatAction")

        if "banned_join_check" in s:
            score += 3
            tags.append("join_check")

        if "kick_participant" in s:
            score += 1
            tags.append("kick")

        if score >= 5:
            found.append((score, f.name, tags))

    except Exception:
        pass

for score, name, tags in sorted(found, reverse=True):
    print(f"⭐ {name}")
    print(f"   امتیاز: {score}")
    print(f"   موارد: {', '.join(tags)}")
    print()

print("تمام شد.")
