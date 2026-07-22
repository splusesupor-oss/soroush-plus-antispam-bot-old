import shutil
from datetime import datetime

FILE="test_main.py"

backup=FILE+".bak_help_format_"+datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE,backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

start=text.find("                help_text = (")

if start == -1:
    print("not found")
    exit()

end=text.find("                )", start)

if end == -1:
    print("end not found")
    exit()

new='''                help_text = (
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
                    "👑 دستورات ادمین‌ها:\\n\\n"
                    "🔤 فیلتر کلمات گروه:\\n"
                    "/فیلتر کلمه\\n"
                    "/رفع کلمه\\n"
                    "/فیلترها\\n\\n"
                    "📊 آمار گروه\\n"
                    "♻️ ریست آمار\\n"
                    "✏️ تغییر اسم گروه\\n"
                    "🗑️ حذف پیام\\n"
                    "🔇 سکوت کاربر\\n"
                    "🔊 رفع سکوت\\n"
                    "🚪 اخراج کاربر\\n"
                    "♻️ آزاد کردن کاربر\\n"
                    "⚠️ صفر کردن تخلفات\\n"
                    "@osine1"
                )'''

text=text[:start]+new+text[end+17:]

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("HELP FORMAT FIXED")
print("BACKUP:",backup)
