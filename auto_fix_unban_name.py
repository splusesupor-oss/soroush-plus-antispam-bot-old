from pathlib import Path
import shutil
from datetime import datetime

p=Path("handlers/message_handler.py")

backup=p.with_name(
    f"message_handler.before_unban_name_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

old=text

text=text.replace(
    "bot.admin_actions.unban(",
    "bot.admin_actions.unban_user("
)

if text != old:
    p.write_text(text,encoding="utf-8")
    print("✅ unban به unban_user تغییر کرد")
else:
    print("⚠️ چیزی تغییر نکرد")

print("📌 بکاپ:",backup)
