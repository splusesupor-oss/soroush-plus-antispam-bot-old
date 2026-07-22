from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip()=="except Exception as e:" and i+1 < len(lines):
        if lines[i+1].strip().startswith("bot.logger.log_error"):
            lines[i+1]="            " + lines[i+1].strip()

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
