from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(len(lines)):
    if 'bot.logger.log_error(f"خطای اخراج: {e}")' in lines[i]:
        lines[i] = "                " + lines[i].strip()
    if 'await event.reply(f"❌ خطا در اخراج:\\n{e}")' in lines[i]:
        lines[i] = "                " + lines[i].strip()

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
