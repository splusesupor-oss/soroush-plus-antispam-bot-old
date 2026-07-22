from pathlib import Path
import shutil,datetime

p=Path("handlers/message_handler.py")

b=Path(
"handlers/message_handler.before_owner_condition_"
+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(p,b)

t=p.read_text(encoding="utf-8")

t=t.replace(
'''if not is_admin(chat_id, sender_username):''',
'''if sender_username != "osine1":''',
2
)

p.write_text(t,encoding="utf-8")

print("✅ انجام شد")
print("📌 بکاپ:",b)
