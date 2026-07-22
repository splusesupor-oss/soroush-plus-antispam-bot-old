import shutil
from datetime import datetime

FILE="test_main.py"

backup = FILE+".bak_games_"+datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE,backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

# حذف بخش های قدیمی راهنما
remove=[
"                    \"😂 جک:\\n\"\n"
"                    \"فقط ارسال کنید:\\n\"\n"
"                    \"جک\\n\\n\"\n",

"                    \"🎯 بازی جرعت حقیقت:\\n\"\n"
"                    \"جرعت → یک جرعت تصادفی دریافت کنید\\n\"\n"
"                    \"حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n\\n\"\n",

"                    \"🧩 چیستان\\n\"\n"
"                    \"یک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن\\n\\n\"\n"
]

for x in remove:
    text=text.replace(x,"")


# اضافه کردن معرفی بازی ها داخل راهنما
old='''                    "✍️ ساخت فونت:\\n"
                    "فونت متن شما\\n\\n"
'''

new='''                    "🎮 برای دریافت بازی ها:\\n"
                    "لیست بازی\\n\\n"

'''+old

text=text.replace(old,new)


# اضافه کردن دستور لیست بازی قبل از راهنما
command='''            if clean_text.strip() == "لیست بازی":
                games_text = (
                    "**🎮 لیست بازی ها:**\\n\\n"
                    "**🧩 چیستان**\\n"
                    "یک چیستان با زمان کم\\n\\n"
                    "**🎯 جرعت - حقیقت**\\n"
                    "یک سوال جرعت یا حقیقت تصادفی\\n\\n"
                    "**🪁 جک**\\n"
                    "یک جک خنده دار تصادفی\\n\\n"
                    "**✒️ جای خالی**\\n"
                    "۳۰ ثانیه برای جواب دادن جای خالی"
                )
                await event.reply(games_text)
                return

'''

marker='            # راهنمای ربات\n'

if marker in text and 'clean_text.strip() == "لیست بازی"' not in text:
    text=text.replace(marker,command+marker)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("GAMES HELP FIXED")
print("BACKUP:",backup)
