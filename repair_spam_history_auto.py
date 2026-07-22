from pathlib import Path
import re

target = Path("handlers/message_handler.py")
text = target.read_text(encoding="utf-8")

backs = [
    Path("handlers/message_handler.py.bak_repeat_ban"),
    Path("handlers/message_handler.py.bak_long_repeat_fix"),
    Path("handlers/message_handler_working_ok.py"),
    Path("handlers/message_handler.py.SAFE_NOW"),
]

# import
if "from modules.spam_history import" not in text:
    for b in backs:
        if b.exists():
            t=b.read_text(encoding="utf-8")
            m=re.search(r'from modules\.spam_history import.*',t)
            if m:
                print("IMPORT RESTORE:",b)
                text=m.group(0)+"\n"+text
                break

# history block
if "save_history_message" not in text or "is_repeat(" not in text:
    for b in backs:
        if b.exists():
            t=b.read_text(encoding="utf-8")
            m=re.search(
                r'\s*save_history_message\(.*?\n.*?if is_repeat\(.*?\):.*?(?=\n\s*(if|try|except|return)|\Z)',
                t,
                re.S
            )
            if m:
                print("HISTORY BLOCK RESTORE:",b)
                insert=text.find("clean_text =")
                text=text[:insert]+m.group(0)+"\n\n"+text[insert:]
                break

target.write_text(text,encoding="utf-8")
print("✅ spam history repaired")
