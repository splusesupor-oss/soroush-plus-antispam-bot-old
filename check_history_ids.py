from pathlib import Path

p=Path("modules/spam_history.py")

print(p.read_text(encoding="utf-8"))
