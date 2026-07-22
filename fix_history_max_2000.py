from pathlib import Path

p = Path("modules/spam_history.py")
text = p.read_text(encoding="utf-8")

backup = Path("modules/spam_history.before_max2000")
backup.write_text(text, encoding="utf-8")

text = text.replace(
    "deque(maxlen=2000)",
    "deque(maxlen=2000)"
)

if "USER_MESSAGE_IDS = defaultdict(lambda: deque(maxlen=2000))" in text:
    print("✅ already 2000")

else:
    text = text.replace(
        "USER_MESSAGE_IDS = defaultdict(lambda: deque(maxlen=100))",
        "USER_MESSAGE_IDS = defaultdict(lambda: deque(maxlen=2000))"
    )

p.write_text(text, encoding="utf-8")

print("✅ history max set to 2000")
print("backup:", backup)
