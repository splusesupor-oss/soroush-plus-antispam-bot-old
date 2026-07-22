from pathlib import Path
import shutil

p = Path("main.py")
backup = "main.py.before_riddle_bold2"

shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

for i, line in enumerate(lines):
    if "for word in [" in line:
        lines.insert(i+1, '                        "🧩 چیستان",')
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("✅ اضافه شد")
        print("📦 بکاپ:", backup)
        break
else:
    print("❌ لیست پیدا نشد")
