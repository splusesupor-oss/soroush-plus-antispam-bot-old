from pathlib import Path
import ast

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

try:
    ast.parse(text)
    print("✅ فایل سالم است")
except SyntaxError as e:
    print("❌ خطا پیدا شد")
    print("نوع:", e.msg)
    print("خط:", e.lineno)

    lines=text.splitlines()
    start=max(0,e.lineno-10)
    end=min(len(lines),e.lineno+10)

    print("\n--- محل خراب ---")
    for i in range(start,end):
        print(f"{i+1}: {lines[i]}")

    print("\n⚠️ این خط نیاز به بازسازی دارد")
