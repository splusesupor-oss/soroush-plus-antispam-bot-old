from pathlib import Path
import shutil
import ast
import re

file = Path("handlers/message_handler.py")

shutil.copy(file, "handlers/message_handler.py.before_deep_repair")

lines = file.read_text(encoding="utf-8").splitlines()


def indent(line):
    return len(line) - len(line.lstrip())


out=[]
i=0

while i < len(lines):

    line=lines[i]

    # except هایی که قبلشان try معتبر نیست
    if line.strip().startswith("except"):

        ex_indent=indent(line)

        found=False

        # دنبال try هم سطح در 80 خط قبل
        for j in range(max(0,i-80),i):

            if lines[j].strip()=="try:" and indent(lines[j])==ex_indent:
                found=True
                break

        if not found:
            print("🔧 fixing orphan except at",i+1)

            # تبدیل except خراب به یک کامنت
            out.append(" "*ex_indent+"# removed orphan except")
            i+=1
            continue


    # try هایی که بعدش بلاک ندارند
    if line.strip()=="try:":
        out.append(line)

        if i+1 < len(lines):
            nxt=lines[i+1]

            if nxt.strip().startswith(("if ","#","except","return")):

                sp=indent(line)

                print("🔧 empty try fixed at",i+1)

                out.append(" "*(sp+4)+"pass")

        i+=1
        continue


    out.append(line)
    i+=1


file.write_text(
    "\n".join(out),
    encoding="utf-8"
)

print("✅ deep repair finished")


try:
    ast.parse("\n".join(out))
    print("✅ Python syntax OK")
except SyntaxError as e:
    print("❌ Remaining:",e.msg,"line",e.lineno)

