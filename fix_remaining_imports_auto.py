from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_remaining_imports.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

imports="""
from modules.spam_history import is_repeat
"""

if "from modules.spam_history import is_repeat" not in text:
    text=imports.strip()+"\n"+text

p.write_text(text,encoding="utf-8")

print("✅ is_repeat import added")
print("backup:",backup)
