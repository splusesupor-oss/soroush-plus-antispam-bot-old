from pathlib import Path

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

# بکاپ
Path("handlers/message_handler.before_try_fix.py").write_text(t,encoding="utf-8")

lines=t.splitlines()

out=[]
skip=False

for i,l in enumerate(lines):
    if i+1==460:
        # بخش راهنما باید یک سطح داخل try باشد
        if l.startswith("        if clean_text.strip() in"):
            l="    "+l
    out.append(l)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ indentation fixed")
