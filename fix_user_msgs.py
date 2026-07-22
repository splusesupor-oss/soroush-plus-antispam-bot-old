from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

insert = False
out = []

for i, line in enumerate(lines):
    if "# فقط پیام‌های تکراری یک کاربر حذف شوند" in line:
        indent = "        "
        out.append(indent + "user_msgs = []")
        out.append(indent + "for m in bot.flood_messages.get(chat_id, []):")
        out.append(indent + "    if m[0] == user_id:")
        out.append(indent + "        user_msgs.append(m)")
        insert = True

    out.append(line)

p.write_text("\n".join(out), encoding="utf-8")

print("✅ user_msgs ساخته شد")
