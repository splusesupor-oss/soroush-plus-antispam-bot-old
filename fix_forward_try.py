from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").splitlines()

for i in range(1315,1335):
    if "except Exception as e:" in lines[i]:
        lines[i] = "        except Exception as e:"
        break

# حذف کامنت‌های تکراری
out=[]
skip=0
for l in lines:
    if l.strip()=="# بررسی تکرار شدید داخل یک پیام":
        skip+=1
        if skip>1:
            continue
    out.append(l)

p.write_text("\n".join(out),encoding="utf-8")
print("FIXED")
