from pathlib import Path
import shutil

file=Path("handlers/message_handler.py")

backup=Path("handlers/message_handler.py.before_fix179")
shutil.copy(file,backup)

lines=file.read_text(encoding="utf-8").splitlines()

start=155
end=180

print("----- OLD -----")
for i in range(start-1,end):
    print(i+1, lines[i])


new=[]

for i,line in enumerate(lines):

    if i==174:   # قبل از خط 175 تقریبی
        pass

    new.append(line)


# پیدا کردن اولین try ناقص قبل از خط 179
for i in range(150,179):
    if lines[i].strip()=="try:":
        try_line=i
        print("TRY FOUND:",try_line+1)
        break
else:
    print("try پیدا نشد")
    exit()


# اضافه کردن except قبل از if جستجو
insert=178

indent=len(lines[try_line])-len(lines[try_line].lstrip())

new_lines=[]

for i,line in enumerate(lines):

    if i==insert:
        new_lines.append(" "*indent+"except Exception as e:")
        new_lines.append(" "*(indent+4)+"bot.logger.log_error(f'خطای اجرای بخش قبل: {e}')")
        new_lines.append(" "*(indent+4)+"pass")

    new_lines.append(line)


file.write_text(
    "\n".join(new_lines),
    encoding="utf-8"
)

print("✅ خط 179 بازسازی شد")

