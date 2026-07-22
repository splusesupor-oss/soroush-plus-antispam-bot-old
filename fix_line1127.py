from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(len(lines)):
    if 'await event.reply(f"❌ خطا در سکوت کاربر:' in lines[i]:
        lines[i] = "                " + lines[i].strip()

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
