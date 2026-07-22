from pathlib import Path
import ast

file = Path("handlers/message_handler.py")

lines = file.read_text(encoding="utf-8").splitlines()

found = 0

while True:
    text = "\n".join(lines)

    try:
        ast.parse(text)
        break
    except SyntaxError as e:
        found += 1
        print("\n==============================")
        print("❌ خطا شماره:", found)
        print("نوع:", e.msg)
        print("خط:", e.lineno)

        start = max(0, e.lineno-8)
        end = min(len(lines), e.lineno+8)

        for i in range(start, end):
            mark = " <<<" if i+1 == e.lineno else ""
            print(f"{i+1}: {lines[i]}{mark}")

        # خط خراب را موقتاً حذف می‌کند تا خط بعدی را هم پیدا کند
        del lines[e.lineno-1]

        if found >= 50:
            print("⛔ بیشتر از 50 خط خراب پیدا شد")
            break

print("\n==============================")
print("تعداد خطاهای پیدا شده:", found)
