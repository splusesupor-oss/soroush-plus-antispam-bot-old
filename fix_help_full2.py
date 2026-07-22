FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

backup=FILE+".bak_help_full2"

with open(backup,"w",encoding="utf-8") as f:
    f.write(text)

start=text.find("# راهنمای ربات")

if start == -1:
    print("START NOT FOUND")
    exit()

end=text.find("for word in [", start)

if end == -1:
    end=text.find("await event.reply", start)

if end == -1:
    print("END NOT FOUND")
    exit()

block=r'''# راهنمای ربات
            if clean_text.strip() in ["راهنما", "/help", "!help", "help"]:
                help_text = (
                    "📌 راهنمای روباه\n\n"
                    "👤 کاربران:\n\n"
                    "💬 پاسخ‌های ساده:\n"
                    "سلام\n"
                    "خوبی\n"
                    "چخبر\n"
                    "چخبرا\n"
                    "مرسی\n"
                    "ممنون\n"
                    "شب بخیر\n\n"

                    "🎮 برای دریافت بازی ها:\n"
                    "لیست بازی\n\n"

                    "✍️ ساخت فونت:\n"
                    "فونت متن شما\n\n"

                    "🛡️ امنیت گروه:\n"
                    "پیام‌های تبلیغاتی، فورواردی، تکراری و هرزنامه‌ها خودکار بررسی می‌شوند.\n\n"

                    "👑 دستورات ادمین‌ها:\n\n"
                    "🔤 فیلتر کلمات گروه:\n"
                    "/فیلتر کلمه\n"
                    "/رفع کلمه\n"
                    "/فیلترها\n\n"

                    "📊 آمار گروه\n"
                    "♻️ ریست آمار\n"
                    "✏️ تغییر اسم گروه\n"
                    "🗑️ حذف پیام\n"
                    "🔇 سکوت کاربر\n"
                    "🔊 رفع سکوت\n"
                    "🚪 اخراج کاربر\n"
                    "♻️ آزاد کردن کاربر\n\n"

                    "⚠️ صفر کردن تخلفات:\n"
                    "@osine1"
                )

'''

text=text[:start]+block+text[end:]

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("HELP REBUILT")
print("BACKUP:",backup)
