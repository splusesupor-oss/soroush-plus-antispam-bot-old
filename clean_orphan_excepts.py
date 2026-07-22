from pathlib import Path
import shutil
import ast

file=Path("handlers/message_handler.py")

shutil.copy(file,"handlers/message_handler.py.before_clean_except")

lines=file.read_text(encoding="utf-8").splitlines()

removed=0

while True:

    try:
        ast.parse("\n".join(lines))
        print("✅ syntax OK")
        break

    except SyntaxError as e:

        line=e.lineno-1

        if line < 0 or line >= len(lines):
            break

        current=lines[line].strip()

        print("ERROR:",e.msg,"LINE:",line+1,current)

        # فقط except خراب
        if current.startswith("except"):
            print("🗑 removing orphan except",line+1)
            del lines[line]
            removed+=1
            continue

        # finally خراب
        if current.startswith("finally"):
            print("🗑 removing orphan finally",line+1)
            del lines[line]
            removed+=1
            continue

        print("⛔ نیاز به بررسی دستی خط",line+1)
        break


file.write_text(
    "\n".join(lines),
    encoding="utf-8"
)

print("Removed:",removed)

