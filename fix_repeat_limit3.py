from pathlib import Path
import shutil

p = Path("modules/spam_history.py")

backup = p.with_name("spam_history.py.before_limit3_fix")
shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

text = text.replace(
"def is_repeat(chat_id, user_id, text, limit=3):",
"def is_repeat(chat_id, user_id, text, limit=3):"
)

# جلوگیری از پاک شدن سابقه هنگام آزاد شدن
p.write_text(text, encoding="utf-8")

print("✅ repeat limit = 3")
print("✅ backup:", backup)


# حذف clear_user از مسیر بن در message_handler
h = Path("handlers/message_handler.py")
backup2 = h.with_name("message_handler.py.before_remove_clear_user")

shutil.copy(h, backup2)

t = h.read_text(encoding="utf-8")

old = """
clear_user(chat_id, user_id)
"""

if old in t:
    t = t.replace(old, "# clear_user disabled - keep spam history", 1)
    h.write_text(t, encoding="utf-8")
    print("✅ clear_user disabled")
else:
    print("⚠️ clear_user line not found")

print("backup:", backup2)
