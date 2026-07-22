from pathlib import Path
import ast

files=list(Path("handlers").glob("message_handler.py*"))

good=[]

for f in files:
    try:
        ast.parse(f.read_text(encoding="utf-8"))
        good.append(f)
        print("✅ OK:",f.name)
    except Exception as e:
        print("❌ BAD:",f.name)

print("\n===== سالم‌ها =====")
for x in good:
    print(x)
