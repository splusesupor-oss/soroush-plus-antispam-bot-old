from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_is_admin_fix.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

if "def is_admin" in text:
    print("is_admin exists")
else:
    imp="from modules.admin_actions import is_admin\n"
    if imp not in text:
        lines=text.splitlines()
        idx=0
        for i,l in enumerate(lines):
            if l.startswith("from ") or l.startswith("import "):
                idx=i+1
        lines.insert(idx,imp.strip())
        text="\n".join(lines)+"\n"
        p.write_text(text,encoding="utf-8")
        print("✅ is_admin import added")

print("backup:",backup)
