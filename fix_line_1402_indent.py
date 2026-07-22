from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

out=[]

for i,l in enumerate(lines, start=1):
    if i == 1402:
        out.append("          except Exception as e:")
        continue

    if i == 1403:
        out.append("              print('خطای بررسی تکرار شدید:', e)")
        continue

    out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ line 1402/1403 fixed")
