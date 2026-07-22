from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_name("message_handler.before_import_restore.py")
shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

imports = """
from modules.group_storage import activate_group, deactivate_group
from modules.spam_history import save_history_message
from modules.fill_game import check_fill
from modules.riddle_game import check_answer
from modules.group_stats import add_message
"""

lines = text.splitlines()

insert = 0
for i,l in enumerate(lines[:80]):
    if l.startswith("import ") or l.startswith("from "):
        insert = i+1

lines.insert(insert, imports.strip())

p.write_text("\n".join(lines)+"\n", encoding="utf-8")

print("✅ imports restored")
print("backup:", backup)
