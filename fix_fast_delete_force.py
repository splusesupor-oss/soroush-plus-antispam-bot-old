from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

backup = Path("handlers/message_handler.before_fast_delete_force")
backup.write_text("\n".join(lines)+"\n", encoding="utf-8")

out=[]
i=0

while i < len(lines):
    line = lines[i]

    if "await bot.client.delete_messages(" in line:
        indent = line[:len(line)-len(line.lstrip())]

        out.append(indent + "import asyncio")
        out.append("")
        out.append(indent + "for x in range(0, len(ids), 100):")
        out.append(indent + "    batch = ids[x:x+100]")
        out.append(indent + "    try:")
        out.append(indent + "        await bot.client.delete_messages(")
        out.append(indent + "            chat_id,")
        out.append(indent + "            batch")
        out.append(indent + "        )")
        out.append(indent + "        await asyncio.sleep(0.2)")
        out.append(indent + "    except Exception as err:")
        out.append(indent + "        print('DELETE ERROR:', err)")

        i += 1
        while i < len(lines) and (")" not in lines[i] or "ids" in lines[i]):
            i += 1
        i += 1
        continue

    out.append(line)
    i += 1

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ force batch delete installed")
print("backup:", backup)
