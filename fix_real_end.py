from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

# حذف return آخر خراب
while lines and lines[-1].strip()=="return":
    lines.pop()

# اضافه کردن پایان صحیح تابع
lines += [
"",
"    except Exception as e:",
"        bot.logger.log_error(f\"خطا در هندل پیام: {e}\")",
"        import traceback",
"        traceback.print_exc()",
]

p.write_text("\n".join(lines),encoding="utf-8")
print("✅ پایان واقعی تابع بسته شد")
