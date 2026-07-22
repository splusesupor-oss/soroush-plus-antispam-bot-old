import ast
import shutil
from pathlib import Path

FILE = Path("main.py")
BACKUP = Path("main.py.auto_repair_backup")

print("🧠 Auto Repair Start")

if not BACKUP.exists():
    shutil.copy2(FILE, BACKUP)
    print("📦 backup:", BACKUP)

s = FILE.read_text(encoding="utf-8")


# 1) پیدا کردن خطاهای syntax
try:
    ast.parse(s)
    print("✅ Syntax OK")
except Exception as e:
    print("❌ Syntax Error:", e)


# 2) پیدا کردن استفاده از متغیر قبل از تعریف (مشکل فعلی text)
try:
    tree = ast.parse(s)

    class Check(ast.NodeVisitor):
        def __init__(self):
            self.assigned=set()
            self.errors=[]

        def visit_Assign(self,node):
            for t in node.targets:
                if isinstance(t,ast.Name):
                    self.assigned.add(t.id)
            self.generic_visit(node)

        def visit_Name(self,node):
            if isinstance(node.ctx,ast.Load):
                if node.id in ["text","chat_id","user_id"] and node.id not in self.assigned:
                    self.errors.append((node.id,node.lineno))
            self.generic_visit(node)

    c=Check()
    c.visit(tree)

    for x in c.errors:
        print("⚠️ استفاده قبل تعریف:",x)

except Exception as e:
    print("scan error",e)


# 3) اصلاح رایج: riddle نباید قبل از تعریف text باشد
if 'if text == "چیستان":' in s:

    pos_riddle=s.find('if text == "چیستان":')
    pos_text=s.find('text = (event.message.message')

    if pos_riddle < pos_text or pos_text == -1:

        print("🔧 moving riddle block")

        start=s.rfind("# RIDDLE_AUTO",0,pos_riddle)
        if start==-1:
            start=pos_riddle

        end=s.find("# کنترل فعال بودن گروه",pos_riddle)

        if end!=-1:
            block=s[start:end]
            s=s[:start]+s[end:]

            marker='clean_text = message_text.strip()'

            idx=s.find(marker)

            if idx!=-1:
                idx=s.find("\n",idx)+1
                s=s[:idx]+"\n"+block.replace("text","clean_text")+s[idx:]
                FILE.write_text(s,encoding="utf-8")
                print("✅ repaired")
            else:
                print("❌ insertion point not found")
        else:
            print("❌ end block not found")

else:
    print("ℹ️ no riddle issue")


# 4) تست نهایی
try:
    ast.parse(FILE.read_text(encoding="utf-8"))
    print("🏁 FINAL: OK")
except Exception as e:
    print("❌ FINAL ERROR:",e)
    shutil.copy2(BACKUP,FILE)
    print("↩ restored backup")

