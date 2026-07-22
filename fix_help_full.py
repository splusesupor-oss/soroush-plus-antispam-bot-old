FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

backup=FILE+".bak_help_full"

with open(backup,"w",encoding="utf-8") as f:
    f.write(text)

start=text.find('help_text = (')

end=text.find('await event.reply(help_text)', start)

if start == -1 or end == -1:
    print("HELP BLOCK NOT FOUND")
    exit()

new_help = '''help_text = (
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
                    "نمایش آمار پیام‌ها و کاربران فعال\\n\\n"

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
                    "سکوت\\n\\n"

                    "🔊 رفع سکوت کاربر:\\n"
                    "رفع سکوت\\n\\n"

                    "🚪 اخراج کاربر:\\n"
                    "اخراج\\n\\n"

                    "♻️ آزاد کردن کاربر:\\n"
                    "آزاد\\n\\n"

                    "⚠️ صفر کردن تخلفات:\\n"
                    "@osine1"
                )
'''

text=text[:start]+new_help+text[end:]

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("HELP FULL REPLACED")
print("BACKUP:",backup)
