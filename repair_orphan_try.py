from pathlib import Path
import shutil
import ast

file = Path("handlers/message_handler.py")

backup = Path("handlers/message_handler.py.before_orphan_fix")
shutil.copy(file, backup)

print("✅ backup created")

lines = file.read_text(encoding="utf-8").splitlines()


fixed=[]
i=0

while i < len(lines):

    line = lines[i]

    # پیدا کردن try هایی که بعدا except ندارند
    if line.strip()=="try:":
        indent=len(line)-len(line.lstrip())

        has_except=False
        end=i+1

        while end < len(lines):

            test=lines[end]

            if test.strip().startswith("except") and (
                len(test)-len(test.lstrip()) == indent
            ):
                has_except=True
                break

            # رسیدن به بلوک هم سطح بعدی
            if test.strip() and (len(test)-len(test.lstrip()) <= indent) and not test.strip().startswith("#"):
                break

            end+=1

        fixed.append(line)

        if not has_except:
            print("🔧 fixing try line", i+1)

            i+=1

            while i < len(lines):

                current=lines[i]

                # قبل از شروع بخش جدید
                if (
                    current.strip().startswith("if ")
                    or current.strip().startswith("#")
                    or current.strip().startswith("try:")
                ) and (len(current)-len(current.lstrip()) <= indent):

                    fixed.append(" "*indent+"except Exception as e:")
                    fixed.append(" "*(indent+4)+"pass")
                    break

                fixed.append(current)
                i+=1

            continue

    fixed.append(line)
    i+=1


file.write_text(
    "\n".join(fixed),
    encoding="utf-8"
)

print("✅ orphan try repaired")

try:
    ast.parse("\n".join(fixed))
    print("✅ AST OK")
except SyntaxError as e:
    print("❌ هنوز خطا:",e.msg,"line",e.lineno)

