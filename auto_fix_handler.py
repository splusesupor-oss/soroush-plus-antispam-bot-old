from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

# حذف بخش خراب بعد از سکوت تا قبل از حذف فوروارد
start = text.find("        # فقط پیام‌های تکراری یک کاربر حذف شوند")
end = text.find("    # حذف پیام های فوروارد شده")

if start == -1 or end == -1:
    print("❌ محدوده پیدا نشد")
    exit()

replacement = """        # فقط پیام‌های تکراری یک کاربر حذف شوند
        try:
            if len(user_msgs) >= 5:
                texts = [x[3] for x in user_msgs]

                normalized = [
                    t.replace(" ", "").replace("\\n", "")
                    for t in texts
                ]

                if len(set(normalized)) > 2:
                    return

                ids = [x[1] for x in user_msgs]

                await bot.client.delete_messages(
                    chat_id,
                    ids
                )

                bot.flood_messages[chat_id] = []

                if chat_id not in bot.delete_notice_lock:
                    bot.delete_notice_lock.add(chat_id)
                    await event.reply(
                        "⚠️ ارسال پیام تکراری پشت سرهم حذف شد"
                    )

        except Exception as e:
            bot.logger.log_error(
                f"خطای ضد فلود: {e}"
            )

"""

text = text[:start] + replacement + text[end:]

# اصلاح تورفتگی های خراب واضح
text = text.replace(
"""        # حذف پیام های فوروارد شده
            try:""",
"""    # حذف پیام های فوروارد شده
        try:"""
)

p.write_text(text, encoding="utf-8")

print("✅ ترمیم خودکار انجام شد")
