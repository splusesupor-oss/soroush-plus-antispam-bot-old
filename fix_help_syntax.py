from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

bad = '''حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\nچیستان → یک معمای تصادفی دریافت کنید 🧩\\n۵۰ ثانیه فرصت دارید\\n\\n"'''

good = '''"حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n"
                      "چیستان → یک معمای تصادفی دریافت کنید 🧩\\n"
                      "۵۰ ثانیه فرصت دارید\\n\\n"'''

if bad in s:
    s = s.replace(bad, good, 1)
    print("✅ Syntax راهنما درست شد")
else:
    print("⚠️ متن خراب پیدا نشد")

p.write_text(s, encoding="utf-8")
