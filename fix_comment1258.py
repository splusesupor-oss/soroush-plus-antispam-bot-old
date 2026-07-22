from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

out=[]
for l in lines:
    if l.strip()=="# پیام سالم - می‌توان برای آنالیز بیشتر لاگ کرد":
        continue
    out.append(l)

p.write_text("\n".join(out),encoding="utf-8")
print("✅ کامنت خراب حذف شد")
