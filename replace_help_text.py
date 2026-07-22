import shutil
from datetime import datetime

FILE="test_main.py"

backup=FILE+".bak_help_replace_"+datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FILE,backup)

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

start=text.find('help_text = (')
if start == -1:
    print("help_text پیدا نشد")
    exit()

end=text.find('                    )', start)

if end == -1:
    print("پایان help_text پیدا نشد")
    exit()

new_help='''help_text = (
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
                    "/فیلتر کلمه  ← افزودن کلمه ممنوعه\\n"
                    "/رفع کلمه  ← حذف کلمه از فیلتر\\n"
                    "/فیلترها  ← نمایش لیست فیلترهای گروه\\n\\n"

                    "📊 آمار گروه\\n"
                    "نمایش آمار پیام‌ها، اعضا و کاربران فعال گروه\\n\\n"

                    "♻️ ریست آمار\\n"
                    "صفر کردن آمار گروه\\n\\n"

                    "✏️ تغییر اسم گروه:\\n"
                    "!اسم نام جدید گروه\\n\\n"

                    "🗑️ حذف پیام:\\n"
                    "پاک\\n"
                    "پاک 10\\n"
                    "پاک 50\\n"
                    "پاک 100\\n\\n"

                    "🔇 سکوت کاربر:\\n"
                    "روی پیام ریپلای کنید و بنویسید:\\n"
                    "سکوت\\n\\n"

                    "🔊 رفع سکوت کاربر:\\n"
                    "رفع سکوت\\n\\n"

                    "🚪 اخراج کاربر:\\n"
                    "اخراج\\n\\n"

                    "♻️ آزاد کردن کاربر:\\n"
                    "آزاد\\n\\n"

                    "⚠️ صفر کردن تخلفات:\\n"
                    "با سازنده ربات تماس بگیرید:\\n"
                    "@osine1"
                )'''

text=text[:start]+new_help+text[end+21:]

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("HELP TEXT COMPLETELY REPLACED")
print("BACKUP:",backup)
