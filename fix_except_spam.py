from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if "bot.logger.log_error(f'خطای بررسی تکرار داخلی: {e}')" in l:
        lines.insert(i, "        except Exception as e:")
        break

p.write_text("\n".join(lines),encoding="utf-8")
print("FIXED")
