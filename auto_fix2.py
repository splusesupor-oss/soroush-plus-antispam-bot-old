from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

# اضافه کردن صفر شدن اخطارها کنار صفر شدن تخلفات
old = "bot.tracker.reset_count(int(gid), user_id)"

new = """bot.tracker.reset_count(int(gid), user_id)
                            try:
                                user_tracker.reset_count(int(gid), user_id)
                            except Exception:
                                pass"""

if "user_tracker.reset_count(int(gid), user_id)" not in text:
    text = text.replace(old, new, 1)
    print("✅ صفر شدن اخطارها اضافه شد")
else:
    print("⚠️ صفر شدن اخطارها قبلا وجود دارد")


# اضافه کردن چک ادمین برای اخطار
old2 = '''if clean_text == "اخطار":
            try:
                if not event.reply_to:'''

new2 = '''if clean_text == "اخطار":
            try:
                sender = await event.get_sender()
                sender_username = getattr(sender, "username", None)

                if not is_admin(chat_id, sender_username):
                    await event.reply("❌ فقط ادمین‌ها اجازه استفاده از اخطار را دارند")
                    return

                if not event.reply_to:'''

if "فقط ادمین‌ها اجازه استفاده از اخطار را دارند" not in text:
    if old2 in text:
        text = text.replace(old2, new2, 1)
        print("✅ محدودیت اخطار برای ادمین‌ها فعال شد")
    else:
        print("⚠️ محل اخطار پیدا نشد")
else:
    print("⚠️ محدودیت اخطار قبلا اضافه شده")


p.write_text(text, encoding="utf-8")
print("✅ پایان اصلاحات")
