from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_reply_safe_fix2"

shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

for i, line in enumerate(lines):
    if "await event.reply(reply)" in line:
        indent = line[:len(line)-len(line.lstrip())]
        lines[i:i+1] = [
            indent + "try:",
            indent + "    await event.reply(reply)",
            indent + "except Exception as e:",
            indent + "    self.logger.log_error(f\"خطای ارسال پاسخ {event.chat_id}: {e}\")"
        ]
        p.write_text("\n".join(lines)+"\n", encoding="utf-8")
        print("✅ درست شد")
        print("📦 بکاپ:", backup)
        break
else:
    print("❌ پیدا نشد")
