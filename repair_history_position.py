from pathlib import Path
import re

target=Path("handlers/message_handler.py")
safe=Path("handlers/message_handler.py.FINAL_SAFE")

t=target.read_text(encoding="utf-8")
s=safe.read_text(encoding="utf-8")

# حذف history تزریق شده خراب
t=re.sub(
    r'\n\s*save_history_message\(.*?print\("🚨 HISTORY REPEAT BAN:", user_id\).*?get_message_ids\(chat_id, user_id\).*?(?=\n\s*clean_text =)',
    '',
    t,
    flags=re.S
)

# گرفتن history از فایل سالم
m=re.search(
    r'\n\s*save_history_message\(.*?print\("🚨 HISTORY REPEAT BAN:", user_id\).*?get_message_ids\(chat_id, user_id\).*?(?=\n\s*clean_text =)',
    s,
    re.S
)

if m:
    pos=t.find("clean_text = message_text.strip()")
    if pos==-1:
        pos=t.find("clean_text =")
    t=t[:pos]+m.group(0)+"\n"+t[pos:]
    print("✅ history moved correctly")

target.write_text(t,encoding="utf-8")
