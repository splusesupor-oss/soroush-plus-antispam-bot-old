from pathlib import Path
import ast
import shutil

target = Path("handlers/message_handler.py")

backups = [
    Path("handlers/message_handler.py.FINAL_SAFE"),
    Path("handlers/message_handler_working_ok.py"),
    Path("handlers/message_handler.py.SAFE_NOW"),
    Path("handlers/message_handler.py.bak"),
]

def get_func(path):
    try:
        t = path.read_text(encoding="utf-8")
        tree = ast.parse(t)
        for n in tree.body:
            if isinstance(n, ast.AsyncFunctionDef) and n.name=="handle_new_message":
                return t[n.lineno-1:n.end_lineno]
    except:
        return None

source = None

for b in backups:
    if b.exists():
        f=get_func(b)
        if f:
            source=f
            print("FOUND:",b)
            break

if not source:
    print("NO SAFE BACKUP")
    exit()

old=target.read_text(encoding="utf-8")

# بکاپ فعلی
shutil.copy(target, target.with_suffix(".before_auto_rebuild"))

# فقط تابع را جایگزین می‌کنیم
tree=ast.parse(old)

lines=old.splitlines()

start=end=None

for n in ast.walk(tree):
    if isinstance(n, ast.AsyncFunctionDef) and n.name=="handle_new_message":
        start=n.lineno-1
        end=n.end_lineno
        break

if start is None:
    print("function not found")
    exit()

new_lines=lines[:start]+source.splitlines()+lines[end:]

target.write_text("\n".join(new_lines)+"\n",encoding="utf-8")

print("✅ handler rebuilt safely")
