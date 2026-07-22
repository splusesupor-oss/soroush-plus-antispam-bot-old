from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

start = None

for i,l in enumerate(lines):
    if l.strip() == "# بررسی تکرار شدید داخل یک پیام":
        start = i
        break

if start is None:
    print("❌ marker not found")
    exit()

end = None
for i in range(start+1, len(lines)):
    if l := lines[i].strip():
        if l == "group_word_spam = False":
            end = i
            break

if end is None:
    print("❌ end not found")
    exit()

block = lines[start:end]

fixed=[]

for line in block:
    if line.strip():
        fixed.append("          " + line)
    else:
        fixed.append("")

lines = lines[:start] + fixed + lines[end:]

p.write_text("\n".join(lines)+"\n", encoding="utf-8")

print("✅ heavy indentation fixed")
