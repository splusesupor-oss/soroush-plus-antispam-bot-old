from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

out=[]
i=0

while i < len(lines):
    if 'print("history error:", e)' in lines[i] or 'خطای تاریخچه: {e}' in lines[i]:
        indent=lines[i].split("p")[0]
        out.append(indent+'print("history error: handled")')
        out.append(indent+'bot.logger.log_error("خطای تاریخچه: handled")')
        i+=1
        continue
    out.append(lines[i])
    i+=1

p.write_text("\n".join(out)+"\n",encoding="utf-8")
print("✅ fixed all history e refs")
