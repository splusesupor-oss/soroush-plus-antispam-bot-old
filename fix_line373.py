from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(len(lines)):
    if 'bot.logger.log_error(f"خطای ارسال پاسخ {event.chat_id}: {e}")' in lines[i]:
        lines[i] = "                " + lines[i].strip()
        if i+1 < len(lines) and lines[i+1].strip()=="return":
            lines[i+1] = "                return"

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
