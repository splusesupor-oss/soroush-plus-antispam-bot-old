from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

# محدود کردن اخطار به ادمین
old = '''            # اخطار کاربر با ریپلای
            if clean_text == "اخطار":
                try:'''

new = '''            # اخطار کاربر با ریپلای (فقط ادمین)
            if clean_text == "اخطار":
                try:
                    sender_check = await event.get_sender()
                    sender_username = getattr(sender_check, "username", None)

                    if not is_admin(chat_id, sender_username):
                        await event.reply("❌ فقط ادمین‌ها اجازه استفاده از اخطار را دارند")
                        return
'''

if old in text:
    text = text.replace(old, new, 1)
    print("✅ دسترسی اخطار اصلاح شد")
else:
    print("⚠️ بخش اخطار قبلاً تغییر کرده یا پیدا نشد")


# صفر کردن اخطار همراه تخلف
old2 = '''bot.tracker.reset_count(int(gid), user_id)
                              reset_groups.append(gid)'''

new2 = '''bot.tracker.reset_count(int(gid), user_id)

                              # صفر کردن اخطارهای کاربر
                              try:
                                  user_tracker.reset_count(int(gid), user_id)
                              except Exception:
                                  pass

                              reset_groups.append(gid)'''

if old2 in text:
    text = text.replace(old2, new2, 1)
    print("✅ صفر شدن اخطار همراه تخلف اضافه شد")
else:
    print("⚠️ محل صفر کردن تخلف پیدا نشد")


p.write_text(text, encoding="utf-8")
print("✅ پایان اصلاحات")
