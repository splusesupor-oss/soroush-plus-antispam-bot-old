from pathlib import Path

p=Path("handlers/message_handler.py")

lines=p.read_text(encoding="utf-8").splitlines()

out=[]
skip=False

for l in lines:
    if l.strip()=="except Exception as ex:" and not skip:
        # فقط except اضافه شده بعد از return را حذف کن
        idx=len(out)
        if idx>0 and "return" in out[-1]:
            skip=True
            continue

    if skip and "history delete error" in l:
        skip=False
        continue

    out.append(l)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ extra except removed")
