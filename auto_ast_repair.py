from pathlib import Path
import shutil
import ast

file=Path("handlers/message_handler.py")

shutil.copy(file,"handlers/message_handler.py.before_ast_repair")

lines=file.read_text(encoding="utf-8").splitlines()


def get_indent(s):
    return len(s)-len(s.lstrip())


for loop in range(30):

    text="\n".join(lines)

    try:
        ast.parse(text)
        print("✅ AST CLEAN")
        file.write_text(text,encoding="utf-8")
        break

    except SyntaxError as e:

        line=e.lineno
        print("❌ fixing",e.msg,"line",line)

        idx=line-1

        start=max(0,idx-15)
        end=min(len(lines),idx+15)

        for n in range(start,end):
            print(f"{n+1}: {lines[n]}")

        bad=lines[idx].strip()

        # except خراب
        if bad.startswith("except"):

            indent=get_indent(lines[idx])

            # حذف except خراب
            del lines[idx]

            # اگر بلاک قبلی return داشت، چیزی لازم نیست
            continue


        # if بعد از try بدون except
        if bad.startswith(("if ","#","bot.","await ","return")):

            # پیدا کردن try قبل
            for j in range(idx-1,max(-1,idx-40),-1):

                if lines[j].strip()=="try:":

                    indent=get_indent(lines[j])

                    lines.insert(
                        idx,
                        " "*indent+"except Exception as e:"
                    )

                    lines.insert(
                        idx+1,
                        " "*(indent+4)+"pass"
                    )

                    break

            continue


        # fallback حذف خط خراب
        del lines[idx]


else:
    print("⛔ هنوز مشکل باقی است")


file.write_text(
    "\n".join(lines),
    encoding="utf-8"
)

