from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

out=[]
done=False

for l in lines:
    if not done and "group_word_spam = False" in l:
        out.append("          except Exception as e:")
        out.append('              print("خطای بررسی تکرار شدید:", e)')
        out.append("")
        done=True

    out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ heavy try closed" if done else "❌ marker not found")
