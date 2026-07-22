from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

out=[]
i=0
while i < len(lines):
    if (lines[i].strip()=="except Exception as e:"
        and i+3 < len(lines)
        and lines[i+1].strip()=="pass"
        and lines[i+2].strip()=="except Exception as e:"):
        out.append(lines[i])
        out.append("            pass")
        i += 2
        continue
    out.append(lines[i])
    i += 1

# fix remaining orphan log line
for i,l in enumerate(out):
    if "خطای بررسی تکرار داخلی" in l:
        out[i]="            bot.logger.log_error(f'خطای بررسی تکرار داخلی: {e}')"

p.write_text("\n".join(out),encoding="utf-8")
print("DONE")
