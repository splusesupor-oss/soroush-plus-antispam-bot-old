from pathlib import Path

s = Path("main.py").read_text(encoding="utf-8")

for key in [
    "event.is_group",
    "event.is_private",
    "message_text =",
    "if not message_text",
    "return"
]:
    print(key, "✅" if key in s else "❌")

print("\nبخش‌های حساس:")
lines = s.splitlines()

for i,l in enumerate(lines,1):
    if "event.is_group" in l or "event.is_private" in l or "NewMessage" in l:
        print(i, l.strip())
