from pathlib import Path
import shutil, ast, time

MAIN=Path("main.py")
BACKUP=Path(f"main.py.before_riddle_ai_{int(time.time())}")

print("🧩 Riddle AI Repair")

if not MAIN.exists():
    print("❌ main.py نیست")
    raise SystemExit

shutil.copy2(MAIN,BACKUP)
print("📦 backup:",BACKUP)

s=MAIN.read_text(encoding="utf-8")

# حذف بلاک‌های ریدل خراب که بیرون ساختار پیام افتاده‌اند
bad_markers=[
    "        # RIDDLE_AUTO",
    "        if text == \"چیستان\":",
    "        if clean_text == \"چیستان\":"
]

start=-1
for m in bad_markers:
    p=s.find(m)
    if p!=-1:
        start=p
        break

if start!=-1:
    # فقط اگر قبلش تعریف درست text وجود ندارد حذف کن
    before=s[:start]
    if "text = " not in before[-1000:]:
        end=s.find("                # پیوی فقط دستور صفر کردن تخلف",start)
        if end!=-1:
            s=s[:start]+s[end:]
            print("🧹 ریدل خراب حذف شد")

MAIN.write_text(s,encoding="utf-8")

try:
    ast.parse(MAIN.read_text(encoding="utf-8"))
    print("✅ Syntax OK")
except Exception as e:
    print("❌ خراب شد، برگشت بکاپ")
    shutil.copy2(BACKUP,MAIN)
    print(e)
    raise SystemExit

print("🏁 Riddle repair done")
