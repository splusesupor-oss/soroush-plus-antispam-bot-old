import shutil
from datetime import datetime

FILE="test_main.py"

backup = FILE + ".bak_help2_" + datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE, backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

old_parts=[
"""                    "😂 جک:\\n"
                    "فقط ارسال کنید:\\n"
                    "جک\\n\\n"
""",
"""                    "🎯 بازی جرعت حقیقت:\\n"
                    "جرعت → یک جرعت تصادفی دریافت کنید\\n"
                    "حقیقت → یک سوال حقیقت تصادفی دریافت کنید\\n\\n"
""",
"""                    "🧩 چیستان\\n"
                    "یک چیستان با زمان کم، ۵۰ ثانیه فرصت برای پاسخ دادن\\n\\n"
"""
]

for old in old_parts:
    text=text.replace(old,"")

new="""                    "🎮 برای دریافت بازی ها:\\n"
                    "لیست بازی\\n\\n"

                    "**🎮 لیست بازی ها:**\\n\\n"
                    "**🧩 چیستان**\\n"
                    "یک چیستان با زمان کم\\n\\n"

                    "**🎯 جرعت - حقیقت**\\n"
                    "یک سوال جرعت یا حقیقت تصادفی\\n\\n"

                    "**🪁 جک**\\n"
                    "یک جک خنده دار تصادفی\\n\\n"

                    "**✒️ جای خالی**\\n"
                    "۳۰ ثانیه برای جواب دادن جای خالی\\n\\n"
"""

target='''                    "✍️ ساخت فونت:\\n"
                    "فونت متن شما\\n\\n"
'''

if target in text:
    text=text.replace(target,new+target)
else:
    print("محل قرار دادن پیدا نشد")

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("DONE")
print("BACKUP:",backup)
