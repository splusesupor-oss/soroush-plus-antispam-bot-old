from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

start = text.find("# اخطار کاربر با ریپلای")
end = text.find("# سکوت کاربر با ریپلای")

if start == -1 or end == -1:
    print("❌ بخش‌ها پیدا نشد")
    raise SystemExit

new = '''# اخطار کاربر با ریپلای
if clean_text == "اخطار":
    try:
        sender = await event.get_sender()
        sender_username = getattr(sender, "username", None)

        from modules.admin_storage import is_admin as real_is_admin

        if not real_is_admin(chat_id, sender_username):
            await event.reply("❌ فقط ادمین‌های ثبت شده اجازه استفاده از اخطار را دارند")
            return

        if not event.reply_to:
            await event.reply("❌ باید روی پیام کاربر ریپلای کنید")
            return

        reply_msg = await bot.client.get_messages(
            chat_id,
            ids=event.reply_to.reply_to_msg_id
        )

        user = await reply_msg.get_sender()

        if not user:
            await event.reply("❌ کاربر پیدا نشد")
            return

        username = getattr(user, "username", None) or "کاربر"

        count = user_tracker.increment(chat_id, user.id)

        if count >= 4:
            ok = await bot.admin_actions.ban_user(chat_id, user.id)

            if ok:
                user_tracker.reset_count(chat_id, user.id)
                await event.reply(
                    f"🚫 کاربر @{username} پس از ۴ اخطار بن شد."
                )
            else:
                await event.reply(
                    f"❌ بن کردن @{username} ناموفق بود."
                )
            return

        await event.reply(
            f"⚠️ کاربر @{username} اخطار دریافت کرد.\\n"
            f"تعداد اخطار: {count}/4"
        )

    except Exception as e:
        await event.reply(f"❌ خطا در اخطار:\\n{e}")

    return

'''

text = text[:start] + new + text[end:]

p.write_text(text, encoding="utf-8")

print("✅ بخش اخطار کامل تمیز شد")
