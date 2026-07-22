from pathlib import Path
import shutil
import ast

target=Path("handlers/message_handler.py")

backs=[
"handlers/message_handler.py.FINAL_SAFE",
"handlers/message_handler_working_ok.py",
"handlers/message_handler.py.SAFE_NOW",
]

for b in backs:
    p=Path(b)
    if p.exists():
        try:
            text=p.read_text(encoding="utf-8")
            ast.parse(text)
            shutil.copy(p,target)
            print("✅ RESTORED FROM:",b)
            break
        except Exception as e:
            print("BAD:",b,e)
else:
    print("❌ NO CLEAN BACKUP FOUND")
    exit()

