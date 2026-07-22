from pathlib import Path
import re

dst=Path("handlers/message_handler.py")

backs=list(Path("handlers").glob("message_handler*.py*"))

target=None

for b in backs:
    try:
        t=b.read_text(encoding="utf-8")
        if "جای خالی" in t and "لیست بازی" in t and "new_fill" in t:
            target=b
            break
    except:
        pass

if not target:
    print("❌ backup game block not found")
    exit()

print("✅ found:",target)

src=target.read_text(encoding="utf-8")
cur=dst.read_text(encoding="utf-8")

# import
if "from modules.fill_blank import new_fill" not in cur:
    cur="from modules.fill_blank import new_fill\n"+cur

# پیدا کردن بخش بازی
m=re.search(r'#.*?جای خالی.*?(?=\n\s*if |\n\s*#)',src,re.S)

if not m:
    print("❌ game block not found")
    exit()

block=m.group(0)

if "جای خالی" not in cur:
    pos=cur.find('if clean_text.strip() in ["راهنما"')
    if pos==-1:
        print("❌ insert point not found")
        exit()

    cur=cur[:pos]+block+"\n\n"+cur[pos:]

dst.write_text(cur,encoding="utf-8")

print("✅ GAMES RESTORED")
