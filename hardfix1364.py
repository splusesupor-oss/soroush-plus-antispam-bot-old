from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

start=next(i for i,l in enumerate(lines) if i>1300 and l.strip()=="except Exception as e:")

for i in range(start+1, start+6):
    if "bot.logger.log_error" in lines[i]:
        lines[i]="        bot.logger.log_error(f'خطای بررسی تکرار داخلی: {e}')"
        break

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
