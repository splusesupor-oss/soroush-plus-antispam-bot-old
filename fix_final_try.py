from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip()=="return" and i>1200:
        lines[i:i+1]=[
            "        except Exception as e:",
            "            bot.logger.log_error(f\"خطا در هندل پیام: {e}\")",
            "            import traceback",
            "            traceback.print_exc()"
        ]
        break

p.write_text("\n".join(lines),encoding="utf-8")
print("✅ try نهایی بسته شد")
