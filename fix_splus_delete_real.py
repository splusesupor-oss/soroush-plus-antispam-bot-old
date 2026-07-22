from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = """await bot.client.delete_messages(
                                    chat_id,
                                    batch
                                )"""

new = """for msg_id in batch:
                                    try:
                                        await bot.client.delete_messages(
                                            chat_id,
                                            msg_id
                                        )
                                    except Exception as delete_error:
                                        print("single delete error:", delete_error)"""

if old not in text:
    print("❌ delete block پیدا نشد")
else:
    text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")
    print("✅ حذف تکی پیام‌ها فعال شد")

