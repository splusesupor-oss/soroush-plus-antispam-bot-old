from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_reply_safe_fix"

shutil.copy(p, backup)

s = p.read_text(encoding="utf-8")

old = """await event.reply(reply)"""

new = """try:
                    await event.reply(reply)
                except Exception as e:
                    self.logger.log_error(f"خطای ارسال پاسخ {event.chat_id}: {e}")"""

if old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("✅ اصلاح شد")
    print("📦 بکاپ:", backup)
else:
    print("❌ خط مورد نظر پیدا نشد")

