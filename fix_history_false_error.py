from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

out=[]

for l in lines:
    if 'bot.logger.log_error("خطای تاریخچه:' in l:
        continue
    out.append(l)

p.write_text("\n".join(out)+"\n",encoding="utf-8")
print("✅ removed fake history errors")
