from pathlib import Path

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

Path("handlers/message_handler.before_help_indent.py").write_text(t,encoding="utf-8")

lines=t.splitlines()

start=None
end=None

for i,l in enumerate(lines):
    if 'if clean_text.strip() in ["راهنما"' in l:
        start=i
    if start is not None and i>start and l.strip()=="return":
        end=i
        break

if start is None:
    print("❌ start not found")
    exit()

if end is None:
    end=start+80

for i in range(start,end):
    if lines[i].strip():
        lines[i]="    "+lines[i]

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ help indent fixed",start+1,end+1)
