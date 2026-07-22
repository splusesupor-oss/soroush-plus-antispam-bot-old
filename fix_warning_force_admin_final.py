from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
done = False

for i,line in enumerate(lines):
    out.append(line)

    if 'if clean_text == "اخطار":' in line and not done:
        indent = line[:len(line)-len(line.lstrip())]

        out.append(indent + "    sender = await event.get_sender()")
        out.append(indent + "    sender_username = getattr(sender, 'username', None)")
        out.append(indent + "    from modules.admin_storage import is_admin as real_is_admin")
        out.append(indent + "")
        out.append(indent + "    if not real_is_admin(chat_id, sender_username):")
        out.append(indent + "        await event.reply('❌ فقط ادمین‌های ثبت شده اجازه استفاده از اخطار را دارند')")
        out.append(indent + "        return")

        done = True

if done:
    p.write_text("\n".join(out), encoding="utf-8")
    print("✅ محدودیت اخطار اضافه شد")
else:
    print("❌ خط اخطار پیدا نشد")
