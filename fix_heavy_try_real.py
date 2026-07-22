from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
fixed = False

for i, l in enumerate(lines):
    # بعد از return مربوط به heavy repeat
    if not fixed and l.strip() == "return":
        # فقط اگر چند خط بعدش group_word_spam باشد
        nxt = "\n".join(lines[i+1:i+8])
        if "group_word_spam" in nxt:
            out.append(l)
            out.append("")
            out.append("          except Exception as e:")
            out.append("              print('خطای بررسی تکرار شدید:', e)")
            fixed = True
            continue

    out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ fixed" if fixed else "❌ not found")
