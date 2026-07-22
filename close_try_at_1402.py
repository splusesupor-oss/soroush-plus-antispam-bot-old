from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

out=[]
done=False

for i,l in enumerate(lines, start=1):

    if i == 1402 and not done:
        out.append("          except Exception as e:")
        out.append("              print('خطای بررسی تکرار شدید:', e)")
        out.append("")
        done=True

    out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ inserted except before line 1402" if done else "❌ failed")
