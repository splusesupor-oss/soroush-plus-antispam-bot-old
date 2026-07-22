from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip()=="except Exception as e:" and i+3 < len(lines):
        if "bot.logger.log_error" in lines[i+1] and "خطای حذف فوروارد" in lines[i+2]:
            lines[i+1]="            bot.logger.log_error("
            lines[i+2]='                f"خطای حذف فوروارد: {e}"'
            lines[i+3]="            )"
            break

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
