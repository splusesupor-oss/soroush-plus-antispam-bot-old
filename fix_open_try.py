from pathlib import Path

p=Path("test_main.py")
lines=p.read_text(encoding="utf-8").splitlines()

target=None
for i,l in enumerate(lines):
    if "if is_spam:" in l:
        target=i
        break

if target is None:
    print("❌ if is_spam پیدا نشد")
    exit()

# پیدا کردن try های باز نزدیک قبل
for i in range(target-1, max(-1,target-80), -1):
    if lines[i].strip()=="try:":
        print("try پیدا شد:", i+1)
        # اگر بعدش except ندارد، حذفش کن
        has_except=False
        for j in range(i+1,target):
            if lines[j].strip().startswith("except"):
                has_except=True
                break
        if not has_except:
            print("حذف try خراب:", i+1)
            del lines[i]
        break

p.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("✅ try خراب بررسی شد")
