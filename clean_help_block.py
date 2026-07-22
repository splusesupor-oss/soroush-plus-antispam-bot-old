import re
import shutil
from datetime import datetime

FILE="test_main.py"

backup=FILE+".bak_fix_"+datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE,backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

new_block = '''            # راهنمای ربات
            if clean_text.strip() in ["راهنما", "/help", "!help", "help"]:
                help_text = (
                    "📌 راهنمای روباه\\n\\n"
                    "👤 کاربران:\\n\\n"
                    "💬 پاسخ‌های ساده:\\n"
                    "سلام\\n"
                    "خوبی\\n"
                    "چخبر\\n"
                    "چخبرا\\n"
                    "مرسی\\n"
                    "ممنون\\n"
                    "شب بخیر\\n\\n"
                    "🎮 برای دریافت بازی ها:\\n"
                    "لیست بازی\\n\\n"
                    "✍️ ساخت فونت:\\n"
                    "فونت متن شما\\n\\n"
                    "🛡️ امنیت گروه:\\n"
                    "پیام‌های تبلیغاتی، فورواردی، تکراری و هرزنامه‌ها خودکار بررسی می‌شوند.\\n\\n"
                )

'''

pattern=r'            # راهنمای ربات\n.*?(?=                return)'

text,count=re.subn(pattern,new_block,text,flags=re.S)

if count:
    with open(FILE,"w",encoding="utf-8") as f:
        f.write(text)
    print("HELP FIXED")
else:
    print("NOT FOUND")

print("BACKUP:",backup)
