from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if 'await event.reply(f"❌ خطا در رفع سکوت:' in l:
        lines[i]="            " + l.strip()

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
