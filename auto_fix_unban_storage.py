from pathlib import Path
import shutil
from datetime import datetime

p=Path("handlers/message_handler.py")

backup=p.with_name(
    f"message_handler.before_unban_storage_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

# اضافه کردن import
if "from modules.banned_storage import" not in text:
    text=text.replace(
        "from modules.admin_storage import",
        "from modules.banned_storage import remove_banned\nfrom modules.admin_storage import"
    )

old="""ok = await bot.admin_actions.unban_user(
                    chat_id,
                    user.id
                )"""

new="""ok = await bot.admin_actions.unban_user(
                    chat_id,
                    user.id
                )

                username = getattr(user, "username", None)
                if username:
                    remove_banned(chat_id, username)"""

if old in text:
    text=text.replace(old,new)
    print("✅ حذف از banned_storage اضافه شد")
else:
    print("⚠️ بلاک unban پیدا نشد")

p.write_text(text,encoding="utf-8")

print("📌 بکاپ:",backup)
