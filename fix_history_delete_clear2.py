from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

backup = Path("handlers/message_handler.before_clear_history2")
backup.write_text("\n".join(lines)+"\n",encoding="utf-8")

out=[]
done=False

for line in lines:
    if 'print(f"🚨 BAN FROM HISTORY' in line and not done:
        indent = line[:len(line)-len(line.lstrip())]

        out.append(indent + "try:")
        out.append(indent + "    clear_user(chat_id, user_id)")
        out.append(indent + "    print(f'🧹 HISTORY CLEARED | user={user_id}')")
        out.append(indent + "except Exception as err:")
        out.append(indent + "    print('CLEAR HISTORY ERROR:', err)")
        out.append("")
        done=True

    out.append(line)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ clear history inserted")
print("backup:", backup)
