from pathlib import Path

p = Path("handlers/message_handler.py")

s = p.read_text(encoding="utf-8").splitlines()

for i in range(1376, 1403):
    if i < len(s):
        line = s[i]
        if line.startswith("            "):
            s[i] = line[2:]

p.write_text("\n".join(s) + "\n", encoding="utf-8")

print("✅ history indent fixed")
