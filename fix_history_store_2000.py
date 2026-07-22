from pathlib import Path

p=Path("modules/spam_history.py")
text=p.read_text(encoding="utf-8")

text=text.replace(
"deque(maxlen=2000)",
"deque(maxlen=2000)"
)

backup=Path("modules/spam_history.py.before_store2000")
backup.write_text(text,encoding="utf-8")

p.write_text(text,encoding="utf-8")

print("✅ history storage already 2000")
print("backup:",backup)
