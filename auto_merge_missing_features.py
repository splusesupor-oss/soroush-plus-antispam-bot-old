from pathlib import Path
import shutil
import re

target = Path("handlers/message_handler.py")

backups = [
    Path("handlers/message_handler.py.bak_repeat_ban"),
    Path("handlers/message_handler.py.bak_long_repeat_fix"),
    Path("handlers/message_handler.py.bak_add_search_help"),
    Path("handlers/message_handler.py.bak_add_fill_game"),
    Path("handlers/message_handler.py.bak_games"),
    Path("handlers/message_handler.py.bak_game_bold"),
    Path("handlers/message_handler_working_ok.py"),
    Path("handlers/message_handler_backup_fix.py"),
]

text = target.read_text(encoding="utf-8")

def add_if_missing(src, patterns):
    global text
    src_text = src.read_text(encoding="utf-8")

    for name, pattern in patterns:
        if not re.search(pattern, text, re.S) and re.search(pattern, src_text, re.S):
            print("ADDING:", name)
            m = re.search(pattern, src_text, re.S)
            block = m.group(0)
            text += "\n\n# AUTO MERGED "+name+"\n"+block+"\n"

checks = [
    ("spam_history",
     r"from modules\.spam_history.*"),
    ("history_repeat",
     r"if is_repeat\(.*?\):.*?(?=\n\s*if |\Z)"),
    ("new_fill",
     r"if clean_text == \"جای خالی\":.*?(?=\n\s*if |\Z)"),
    ("games_list",
     r"if clean_text\.strip\(\) in \[\"لیست بازی\".*?(?=\n\s*if |\Z)"),
    ("search",
     r"if clean_text\.startswith\(\"جستجو \"\):.*?(?=\n\s*if |\Z)"),
]

for b in backups:
    if b.exists():
        print("CHECK BACKUP:", b)
        add_if_missing(b, checks)

target.write_text(text, encoding="utf-8")

print("✅ MERGE DONE")
