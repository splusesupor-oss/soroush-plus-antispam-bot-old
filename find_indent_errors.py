from pathlib import Path
import ast

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

try:
    ast.parse(text)
    print("OK")
except IndentationError as e:
    print("LINE:", e.lineno)
    print("MSG :", e.msg)
    lines = text.splitlines()
    start = max(0, e.lineno-5)
    end = min(len(lines), e.lineno+5)
    for i in range(start, end):
        print(f"{i+1}: {repr(lines[i])}")
except SyntaxError as e:
    print("LINE:", e.lineno)
    print("MSG :", e.msg)
    lines = text.splitlines()
    start = max(0, e.lineno-5)
    end = min(len(lines), e.lineno+5)
    for i in range(start, end):
        print(f"{i+1}: {repr(lines[i])}")
