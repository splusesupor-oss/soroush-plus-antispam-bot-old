from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_import_fix2.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

bad=[
"from modules.fill_game import check_fill\n",
"from modules.riddle_game import check_answer\n",
"from modules.group_stats import add_message\n"
]

for x in bad:
    text=text.replace(x,"")

p.write_text(text,encoding="utf-8")

print("✅ wrong imports removed")
print("backup:",backup)
