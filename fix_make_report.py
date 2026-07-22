from pathlib import Path

p = Path("handlers/message_handler.py")
t = p.read_text(encoding="utf-8")

imp = "from modules.group_stats import make_report"

if imp not in t:
    lines = t.splitlines()
    i = 0
    while i < len(lines) and (lines[i].startswith("from ") or lines[i].startswith("import ")):
        i += 1
    lines.insert(i, imp)
    t = "\n".join(lines)

p.write_text(t, encoding="utf-8")

print("✅ make_report fixed")
