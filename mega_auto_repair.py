from pathlib import Path
import ast
import shutil
import re

FILE = Path("handlers/message_handler.py")

if not FILE.exists():
    print("❌ فایل پیدا نشد")
    exit()

backup = FILE.with_suffix(".py.mega_backup")
shutil.copy(FILE, backup)

print("✅ Backup:", backup)

lines = FILE.read_text(encoding="utf-8").splitlines()


def fix_except_indent(lines):
    out=[]
    i=0

    while i < len(lines):
        line=lines[i]

        # except هایی که بیشتر از try هم‌سطح هستند
        if re.match(r'^\s+except Exception as e:', line):
            indent=len(line)-len(line.lstrip())

            if i>0:
                prev=lines[i-1]
                prev_indent=len(prev)-len(prev.lstrip())

                if indent > prev_indent+4:
                    line=" "*prev_indent+"except Exception as e:"

        out.append(line)
        i+=1

    return out


def remove_orphan_except(lines):
    out=[]
    for i,line in enumerate(lines):

        if line.strip().startswith("except Exception as e:"):

            # اگر قبلش try نیست، حداقل چند خط قبل را چک کن
            found=False

            for j in range(max(0,i-20),i):
                if lines[j].strip().startswith("try:"):
                    found=True
                    break

            if not found:
                print("⚠️ حذف except بی صاحب خط",i+1)
                continue

        out.append(line)

    return out


def repair_common_blocks(lines):

    out=[]

    for i,line in enumerate(lines):

        # الگوهای خراب:
        # return
        # except
        if line.strip()=="return":
            out.append(line)

            if i+1<len(lines):
                nxt=lines[i+1]

                if nxt.strip().startswith("except"):
                    # except باید هم سطح try باشد
                    fixed=nxt.lstrip()
                    out.append("        "+fixed)
                    continue

            continue

        out.append(line)

    return out


for round_no in range(10):

    print("\n🔧 مرحله",round_no+1)

    lines=fix_except_indent(lines)
    lines=remove_orphan_except(lines)
    lines=repair_common_blocks(lines)

    text="\n".join(lines)

    try:
        ast.parse(text)
        print("✅ Syntax سالم شد")
        break

    except SyntaxError as e:

        print(
            "❌ خطا:",
            e.msg,
            "line:",
            e.lineno
        )

        start=max(0,e.lineno-3)
        end=min(len(lines),e.lineno+3)

        for n in range(start,end):
            print(
                n+1,
                lines[n]
            )

        # خط خراب را علامت می‌زنیم ولی حذف نمی‌کنیم
        if e.lineno and e.lineno<=len(lines):
            if "except" in lines[e.lineno-1]:
                lines[e.lineno-1]="        pass"


FILE.write_text(
    "\n".join(lines),
    encoding="utf-8"
)

print("\n✅ بازسازی تمام شد")

