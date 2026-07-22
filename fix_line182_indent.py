from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if "BAN FROM HISTORY" in l:
        print("found:", i+1)

# یکدست کردن بلاک اطراف خط مشکل
for i in range(150,210):
    if i < len(lines):
        line = lines[i]
        if line.strip().startswith(("print(", "try:", "except ", "return", "ids =", "for ", "clear_user", "await")):
            if i >= 150:
                lines[i] = "                  " + line.strip()

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ indent fixed")
