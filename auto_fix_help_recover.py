import glob
import shutil
import subprocess
from datetime import datetime

FILE="test_main.py"

# پیدا کردن بکاپ‌ها
backs=sorted(glob.glob("test_main.py.bak*"), key=lambda x: x)

if backs:
    backup_source=backs[0]
    print("RESTORE FROM:", backup_source)
    shutil.copy(backup_source, FILE)

# بکاپ جدید
backup=FILE+".bak_auto_"+datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE, backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

start=text.find("            # راهنمای ربات")

if start == -1:
    print("HELP NOT FOUND")
    exit()

end=text.find("                return", start)

if end == -1:
    print("END NOT FOUND")
    exit()

new='''            # راهنمای ربات
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

text=text[:start]+new+text[end:]

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("HELP AUTO FIXED")
print("BACKUP:",backup)

# تست
result=subprocess.run(["python3","-m","py_compile",FILE],capture_output=True,text=True)

if result.returncode==0:
    print("PYTHON OK")
else:
    print(result.stderr)
