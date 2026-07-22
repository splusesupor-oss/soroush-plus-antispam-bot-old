from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
i = 0
changed = False

while i < len(lines):
    line = lines[i]

    if "await bot.client.delete_messages(" in line and "batch" in "\n".join(lines[i:i+5]):
        indent = line[:len(line)-len(line.lstrip())]

        out.append(indent + "for msg_id in batch:")
        out.append(indent + "    try:")
        out.append(indent + "        await bot.client.delete_messages(")
        out.append(indent + "            chat_id,")
        out.append(indent + "            msg_id")
        out.append(indent + "        )")

        # رد شدن از بلوک قبلی حذف
        i += 1
        while i < len(lines) and "except Exception as delete_error" not in lines[i]:
            i += 1

        if i < len(lines):
            out.append(indent + "    except Exception as delete_error:")
            out.append(indent + "        print('fast delete error:', delete_error)")
            i += 1

        changed = True
        continue

    out.append(line)
    i += 1

if changed:
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("✅ حذف اجباری تک‌پیام فعال شد")
else:
    print("❌ خط حذف پیدا نشد")
