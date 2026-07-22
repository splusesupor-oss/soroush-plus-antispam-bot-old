from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

# اضافه کردن ذخیره قبل از HEAVY BAN
old = 'print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)'

new = '''print("🚨 HEAVY REPEAT SPAM BAN:", username, user_id)

                # ذخیره پیام اسپم برای حذف کامل
                try:
                    if not hasattr(bot, "spammer_messages"):
                        bot.spammer_messages = {}

                    if user_id not in bot.spammer_messages:
                        bot.spammer_messages[user_id] = []

                    bot.spammer_messages[user_id].append(event.message.id)

                    # حذف سریع همه پیام های ذخیره شده
                    ids = list(bot.spammer_messages[user_id])
                    if ids:
                        await bot.client.delete_messages(ids)

                    bot.spammer_messages[user_id] = []

                except Exception as e:
                    print("SPAM DELETE HISTORY ERROR:", e)
'''

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ ذخیره و حذف اسپم سنگین اضافه شد")
else:
    print("❌ HEAVY BAN پیدا نشد")
