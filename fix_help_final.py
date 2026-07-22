import shutil
from datetime import datetime

FILE="test_main.py"

backup=FILE+".bak_help_final_"+datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE,backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

old='''🎮 برای دریافت بازی ها:
لیست بازی

🎮 برای دریافت بازی ها:
لیست بازی

🎮 برای دریافت بازی ها:
لیست بازی
'''

new='''🎮 برای دریافت بازی ها:
لیست بازی

'''

text=text.replace(old,new)

old_games='''😂 جک:
فقط ارسال کنید:
جک

🎯 بازی جرعت حقیقت:
جرعت → یک جرعت تصادفی دریافت کنید
حقیقت → یک سوال حقیقت تصادفی دریافت کنید

🧩 چیستان
یک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن

'''

text=text.replace(old_games,new)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("HELP FINAL FIXED")
print("BACKUP:",backup)
