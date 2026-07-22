from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

out=[]
skip=False

for i,l in enumerate(lines):
    if l.strip()=="except Exception as e:" and i>0:
        if lines[i-1].strip()=="pass" and i+1 < len(lines):
            if "bot.logger.log_error" in lines[i+1]:
                out.append(l)
                out.append("            pass")
                skip=True
                continue

    if skip:
        if "bot.logger.log_error" in l:
            out.append("            " + l.strip())
            skip=False
        continue

    out.append(l)

p.write_text("\n".join(out),encoding="utf-8")
print("FIXED")
