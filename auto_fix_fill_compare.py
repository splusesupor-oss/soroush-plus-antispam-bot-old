from pathlib import Path
import shutil, time

p=Path("modules/fill_blank.py")

backup=f"modules/fill_blank.before_compare_fix_{time.strftime('%Y%m%d_%H%M%S')}.py"
shutil.copy(p, backup)

text=p.read_text(encoding="utf-8")

old='''    if answer.strip()==data["answer"]:
        score[user_id]=score.get(user_id,0)+1
        del active_fill[key]
        return True
'''

new='''    user_answer = answer.strip().replace(" ", "").replace("‌", "")
    correct_answer = data["answer"].strip().replace(" ", "").replace("‌", "")

    if user_answer == correct_answer:
        score[user_id]=score.get(user_id,0)+1
        del active_fill[key]
        return True
'''

if old in text:
    text=text.replace(old,new)
    p.write_text(text,encoding="utf-8")
    print("✅ مقایسه جواب جای خالی اصلاح شد")
else:
    print("⚠️ بخش پیدا نشد")

print("📌 بکاپ:",backup)
