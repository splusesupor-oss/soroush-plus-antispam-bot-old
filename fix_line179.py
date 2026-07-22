from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

new=[]

for l in lines:
    if "خطای تاریخچه:" in l or "history error:" in l:
        indent=l[:len(l)-len(l.lstrip())]
        new.append(indent+'bot.logger.log_error("خطای تاریخچه ثبت شد")')
    else:
        new.append(l)

p.write_text("\n".join(new)+"\n",encoding="utf-8")
print("✅ cleaned history lines")
