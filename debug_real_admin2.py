from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
done = False

for line in lines:
    out.append(line)

    if "if not is_admin(chat_id, sender_username):" in line and not done:
        indent = line[:len(line)-len(line.lstrip())]
        out.append(indent + '    print("DEBUG WARNING ADMIN:", chat_id, sender_username, is_admin(chat_id, sender_username))')
        done = True

if done:
    p.write_text("\n".join(out), encoding="utf-8")
    print("✅ دیباگ اضافه شد")
else:
    print("❌ خط if not is_admin پیدا نشد")
