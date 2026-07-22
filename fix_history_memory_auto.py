from pathlib import Path
import re

# 1) افزایش حافظه تاریخچه
p = Path("modules/spam_history.py")

if p.exists():
    t = p.read_text(encoding="utf-8")

    t = t.replace(
        "maxlen=100",
        "maxlen=1000"
    )

    p.write_text(t, encoding="utf-8")
    print("✅ spam_history maxlen -> 1000")

else:
    print("❌ spam_history.py not found")


# 2) حذف پاک کردن تاریخچه بعد از بن
p = Path("handlers/message_handler.py")

if p.exists():
    t = p.read_text(encoding="utf-8")

    old = """
                clear_user(chat_id, user_id)
                return
"""

    new = """
                # history kept for future spam detection
                return
"""

    if old in t:
        t = t.replace(old, new)
        print("✅ clear_user disabled after ban")
    else:
        print("⚠️ clear_user block not found")

    p.write_text(t, encoding="utf-8")

else:
    print("❌ handler not found")


# 3) تست syntax
import subprocess

r = subprocess.run(
    ["python3","-m","py_compile","handlers/message_handler.py"],
    capture_output=True,
    text=True
)

if r.returncode == 0:
    print("✅ COMPILE OK")
else:
    print("❌ COMPILE ERROR")
    print(r.stderr)

print("✅ DONE")
