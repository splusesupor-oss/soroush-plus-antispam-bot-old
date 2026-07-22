from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

line = '                      "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n\\n"'

insert = '''                      "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n"
                      "چیستان → یک معمای تصادفی دریافت کنید 🧩\\n"
                      "۵۰ ثانیه فرصت دارید جواب بدهید\\n\\n"'''

if line in s:
    s = s.replace(line, insert, 1)
    print("✅ چیستان به راهنما اضافه شد")
else:
    print("⚠️ خط پیدا نشد، جستجوی جایگزین")

    old = '"حقیقت → یک سوال حقیقت تصادفی دریافت کنید'
    pos = s.find(old)

    if pos != -1:
        end = s.find('\\n', pos)
        s = s[:pos] + 'حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\nچیستان → یک معمای تصادفی دریافت کنید 🧩\\n۵۰ ثانیه فرصت دارید' + s[end:]
        print("✅ با روش دوم اضافه شد")
    else:
        print("❌ اصلا پیدا نشد")

p.write_text(s, encoding="utf-8")
