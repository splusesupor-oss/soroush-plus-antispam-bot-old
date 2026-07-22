from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

print("تعداد اخطارها:", text.count('if clean_text == "اخطار"'))

for i,line in enumerate(text.splitlines(),1):
    if 'if clean_text == "اخطار"' in line:
        print("خط فعال:", i)
