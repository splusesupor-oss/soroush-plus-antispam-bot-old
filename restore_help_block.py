from pathlib import Path
import re

dst=Path("handlers/message_handler.py")

backs=list(Path("handlers").glob("message_handler*.py*"))

src=None
for b in backs:
    try:
        t=b.read_text(encoding="utf-8")
        if 'if clean_text.strip() in ["راهنما"' in t and "MessageEntityBold" in t:
            src=t
            print("✅ backup:",b)
            break
    except:
        pass

if not src:
    print("❌ backup not found")
    exit()

cur=dst.read_text(encoding="utf-8")

# حذف راهنمای خراب فعلی
a=cur.find('if clean_text.strip() in ["راهنما"')
b=cur.find('if clean_text.startswith(("!", "/", ".")):')

if a==-1 or b==-1:
    print("❌ current block not found")
    exit()

# گرفتن بلاک سالم
sa=src.find('if clean_text.strip() in ["راهنما"')
sb=src.find('if clean_text.startswith(("!", "/", ".")):')

block=src[sa:sb]

cur=cur[:a]+block+"\n\n"+cur[b:]

dst.write_text(cur,encoding="utf-8")

print("✅ HELP RESTORED")
