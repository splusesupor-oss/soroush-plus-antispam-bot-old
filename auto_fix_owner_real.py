from pathlib import Path
import shutil
import datetime

file=Path("handlers/message_handler.py")

backup=Path(
    "handlers/message_handler.before_owner_real_fix_"
    + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".py"
)

shutil.copy(file, backup)

lines=file.read_text(encoding="utf-8").splitlines()

out=[]
i=0
changed=0

while i < len(lines):

    line=lines[i]

    # فقط بخش ثبت ادمین
    if 'if clean_text.startswith("ثبت ادمین")' in line:
        out.append(line)
        i+=1

        while i < len(lines) and 'try:' not in lines[i]:
            if 'if not is_admin(chat_id, sender_username):' in lines[i]:
                indent=lines[i].split('if')[0]
                out.append(indent+'if sender_username != "osine1":')
                i+=1
                out.append(indent+'    await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")')
                out.append(indent+'    return')

                # سه خط قدیمی را رد کن
                while i < len(lines) and ('await event.reply' not in lines[i] or 'return' not in lines[i]):
                    i+=1
                changed+=1
                continue

            out.append(lines[i])
            i+=1
        continue

    out.append(line)
    i+=1


file.write_text("\n".join(out)+"\n",encoding="utf-8")

print("اصلاح شد:",changed)
print("بکاپ:",backup)
