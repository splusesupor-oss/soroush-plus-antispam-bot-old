from pathlib import Path

# افزایش حافظه تاریخچه
p = Path("modules/spam_history.py")
text = p.read_text(encoding="utf-8")

text = text.replace(
    "deque(maxlen=300)",
    "deque(maxlen=2000)"
)

p.write_text(text, encoding="utf-8")


# اصلاح حذف سریع
p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

start = text.find("ids = get_message_ids(chat_id, user_id)")

if start == -1:
    print("❌ بخش تاریخچه پیدا نشد")
    exit()

end = text.find(
    'print(f"🚨 BAN FROM HISTORY',
    start
)

old = text[start:end]

new = '''ids = get_message_ids(chat_id, user_id)

                if ids:
                    for i in range(0, len(ids), 100):
                        batch = ids[i:i+100]
                        try:
                            await bot.client.delete_messages(
                                chat_id,
                                batch
                            )
                        except Exception as delete_error:
                            print("fast history delete error:", delete_error)

                '''

text = text[:start] + new + text[end:]

p.write_text(text, encoding="utf-8")

print("✅ حذف سریع 100 تایی + تاریخچه بزرگ فعال شد")
