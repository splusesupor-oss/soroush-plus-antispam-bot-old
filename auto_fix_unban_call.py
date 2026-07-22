from pathlib import Path
import shutil,datetime

p=Path("handlers/message_handler.py")

backup=p.with_name(
    "message_handler.before_unban_call_fix_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

old="bot.admin_actions.unban("
new="bot.admin_actions.unban_user("

if old in text:
    text=text.replace(old,new)
    p.write_text(text,encoding="utf-8")
    print("✅ unban به unban_user تغییر کرد")
else:
    print("⚠️ فراخوانی unban پیدا نشد")

print("📌 بکاپ:",backup)
