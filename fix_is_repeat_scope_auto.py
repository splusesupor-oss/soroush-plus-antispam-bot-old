from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_is_repeat_scope_fix.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

# حذف ایمپورت تکراری
text=text.replace("from modules.spam_history import is_repeat\n","")

# قرار دادن بعد از import های اصلی
lines=text.splitlines()

idx=0
for i,l in enumerate(lines):
    if l.startswith("from ") or l.startswith("import "):
        idx=i+1

lines.insert(idx,"from modules.spam_history import is_repeat")

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ is_repeat scope fixed")
print("backup:",backup)
