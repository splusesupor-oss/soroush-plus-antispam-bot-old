from pathlib import Path
import ast

file = Path("handlers/message_handler.py")

text = file.read_text(encoding="utf-8")

try:
    ast.parse(text)
    print("✅ فایل سالم است")
except SyntaxError as e:
    print("❌ Syntax Error")
    print("نوع:", e.msg)
    print("خط:", e.lineno)
    print("ستون:", e.offset)

    lines = text.splitlines()

    start=max(0,e.lineno-15)
    end=min(len(lines),e.lineno+15)

    print("\n--- محل خراب ---")
    for i in range(start,end):
        print(f"{i+1}: {lines[i]}")
