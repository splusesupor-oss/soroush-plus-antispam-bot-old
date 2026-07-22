from pathlib import Path

p=Path("handlers/message_handler.py")
lines=p.read_text(encoding="utf-8").expandtabs(4).splitlines()

# پیدا کردن except خراب قبل از تاریخچه
start=None

for i,l in enumerate(lines):
    if "خطای بررسی کلمات گروه" in l:
        start=i+1
        break

if start is None:
    print("not found")
    exit()

# تا بررسی اسپم
end=None
for i in range(start,len(lines)):
    if "# بررسی اسپم" in lines[i]:
        end=i
        break

if end is None:
    print("end not found")
    exit()

# فقط بخش بین این دو را استاندارد کن
new=[]

for l in lines[start:end]:
    if l.strip()=="":
        new.append("")
        continue

    # حذف فاصله اضافی اول
    stripped=l.lstrip()

    # سطح تابع
    if stripped.startswith("# ذخیره تاریخچه"):
        new.append("          "+stripped)
    elif stripped.startswith("try:"):
        new.append("          "+stripped)
    elif stripped.startswith("except Exception"):
        new.append("          "+stripped)
    elif stripped.startswith("add_message"):
        new.append("              "+stripped)
    elif stripped.startswith("print("):
        new.append("              "+stripped)
    elif stripped.startswith("# بررسی تاریخچه"):
        new.append("          "+stripped)
    elif stripped.startswith("if is_repeat"):
        new.append("              "+stripped)
    elif stripped.startswith("return"):
        new.append("                  "+stripped)
    else:
        new.append(l)

lines[start:end]=new

p.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("fixed parent block")
