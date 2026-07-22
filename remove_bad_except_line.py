from pathlib import Path

p = Path("handlers/message_handler.py")

lines = p.read_text(encoding="utf-8").splitlines()

out = []
skip = False

for l in lines:
    if l.strip() == "except Exception as ex:":
        # فقط همان except بعد از return را حذف کن
        if len(out) > 0 and out[-1].strip() == "return":
            skip = True
            continue

    if skip:
        if "history delete error" in l:
            skip = False
            continue
        else:
            skip = False

    out.append(l)

p.write_text("\n".join(out)+"\n", encoding="utf-8")

print("✅ removed")
