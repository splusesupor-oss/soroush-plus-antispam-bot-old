from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_help_riddle_add2"

shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

for i, line in enumerate(lines):
    if "حقیقت → یک سوال حقیقت تصادفی دریافت کنید" in line:
        indent = line[:len(line)-len(line.lstrip())]
        lines.insert(i+1, indent + '"**🧩 چیستان**\\n"')
        lines.insert(i+2, indent + '"یک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن\\n\\n"')
        p.write_text("\n".join(lines)+"\n", encoding="utf-8")
        print("✅ اضافه شد")
        print("📦 بکاپ:", backup)
        break
else:
    print("❌ خط حقیقت پیدا نشد")
