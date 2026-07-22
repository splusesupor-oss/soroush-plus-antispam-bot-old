FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    lines=f.readlines()

start=None
end=None

for i,l in enumerate(lines):
    if '# راهنمای ربات' in l:
        start=i
    if start is not None and i>start and 'chat = await event.get_chat()' in l:
        end=i
        break

if start is None or end is None:
    print("HELP BLOCK NOT FOUND")
    exit()

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
                    "♻️ آزاد کردن کاربر\\n\\n"

                    "⚠️ صفر کردن تخلفات:\\n"
                    "@osine1"
                )

                await event.reply(help_text)
                return

'''

lines = lines[:start] + [new_block] + lines[end:]

with open(FILE,"w",encoding="utf-8") as f:
    f.writelines(lines)

print("HELP REPAIRED COMPLETELY")
