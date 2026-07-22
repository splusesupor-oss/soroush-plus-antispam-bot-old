from pathlib import Path
import re

target=Path("handlers/message_handler.py")
source=Path("handlers/message_handler.py.FINAL_SAFE")

t=target.read_text(encoding="utf-8")
s=source.read_text(encoding="utf-8")

# import
if "from modules.spam_history import" not in t:
    imp=re.search(r"from modules\.spam_history import.*",s)
    if imp:
        lines=t.splitlines()
        lines.insert(0,imp.group(0))
        t="\n".join(lines)+"\n"

# block
block=re.search(
r"\s*save_history_message\(\s*chat_id,.*?if is_repeat\(chat_id, user_id, message_text\):.*?(?=\n\s*#|\n\s*if|\n\s*try)",
s,
re.S
)

if block and "HISTORY REPEAT BAN" not in t:
    pos=t.find("clean_text = message_text.strip()")
    if pos==-1:
        pos=t.find("clean_text =")
    t=t[:pos]+block.group(0)+"\n\n"+t[pos:]
    print("✅ history block copied")

target.write_text(t,encoding="utf-8")
print("DONE")
