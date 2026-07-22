from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_real_imports.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

add="""
from modules.fill_blank import check_fill
from modules.riddles import check_answer
from modules.group_stats import add_message
"""

if "from modules.fill_blank import check_fill" not in text:
    text=add.strip()+"\n"+text

p.write_text(text,encoding="utf-8")

print("✅ real imports added")
print("backup:",backup)
