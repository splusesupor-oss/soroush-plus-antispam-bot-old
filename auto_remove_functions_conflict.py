from pathlib import Path
import shutil,datetime

p=Path("handlers/message_handler.py")

backup=Path(
    "handlers/message_handler.before_remove_functions_conflict_"+
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".py"
)

shutil.copy(p,backup)

lines=p.read_text(encoding="utf-8").splitlines()

out=[]
skip=0

for line in lines:
    if line.strip()=="global functions":
        skip=2
        continue

    if skip:
        skip-=1
        continue

    out.append(line)

p.write_text("\n".join(out)+"\n",encoding="utf-8")

print("✅ تداخل functions حذف شد")
print("📌 بکاپ:",backup)
