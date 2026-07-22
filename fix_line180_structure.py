from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

backup=Path("handlers/message_handler.before_line180_fix")
backup.write_text("\n".join(lines)+"\n",encoding="utf-8")

out=[]
skip=False

for line in lines:
    if 'print(f"🧹 ALL HISTORY DELETED | count={len(ids)}")' in line:
        out.append("                          clear_user(chat_id, user_id)")
        out.append("                          print(f\"🧹 ALL HISTORY DELETED | count={len(ids)}\")")
        skip=False
    else:
        out.append(line)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ line structure fixed")
print("backup:",backup)
