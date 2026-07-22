from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

for i,l in enumerate(lines):
    if l.strip() == "except Exception as e:" and i > 1200:
        # اگر except آخر فایل است، تورفتگی بدنه را درست کن
        lines[i] = "        except Exception as e:"
        if i+1 < len(lines):
            lines[i+1] = "            bot.logger.log_error(f\"خطا در هندل پیام: {e}\")"
        if i+2 < len(lines):
            lines[i+2] = "            import traceback"
        if i+3 < len(lines):
            lines[i+3] = "            traceback.print_exc()"
        break

p.write_text("\n".join(lines), encoding="utf-8")
print("✅ except آخر اصلاح شد")
