from pathlib import Path

p = Path("modules/spam_history.py")
text = p.read_text(encoding="utf-8")

text = text.replace(
    "deque(maxlen=100)",
    "deque(maxlen=2000)"
)

text = text.replace(
    "limit=5",
    "limit=3"
)

p.write_text(text, encoding="utf-8")

print("✅ Splus history updated")
