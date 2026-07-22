import shutil
from datetime import datetime

FILE="test_main.py"

backup=FILE+".bak_games_clean_"+datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE, backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

# حذف همه بخش‌های قبلی بازی
start=text.find("            # لیست بازی ها")
if start != -1:
    end=text.find("            # راهنمای ربات", start)
    if end != -1:
        text=text[:start]+text[end:]

# حذف نوشته‌های قدیمی داخل راهنما
old1='''😂 جک:
فقط ارسال کنید:
جک

🎯 بازی جرعت حقیقت:
جرعت → یک جرعت تصادفی دریافت کنید
حقیقت → یک سوال حقیقت تصادفی دریافت کنید

🧩 چیستان
یک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن
'''

new1='''🎮 برای دریافت بازی ها:
لیست بازی

'''

text=text.replace(old1,new1)


# اضافه کردن دستور لیست بازی فقط یک بار
command='''            if clean_text.strip() == "لیست بازی":
                await event.reply(
                    "**🎮 لیست بازی ها:**\\n\\n"
                    "🧩 چیستان\\n"
                    "یک چیستان با فرصت کم\\n\\n"
                    "🎯 جرعت - حقیقت\\n"
                    "سوال جرعت یا حقیقت تصادفی\\n\\n"
                    "🪁 جک\\n"
                    "جک های خنده دار\\n\\n"
                    "✒️ جای خالی\\n"
                    "۳۰ ثانیه برای جواب دادن جای خالی"
                )
                return

'''

marker="            # راهنمای ربات\n"

if "clean_text.strip() == \"لیست بازی\"" not in text:
    text=text.replace(marker,command+marker)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("GAMES CLEAN FIXED")
print("BACKUP:",backup)
