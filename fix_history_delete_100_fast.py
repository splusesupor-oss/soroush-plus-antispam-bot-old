from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = """if ids:
                        for i in range(0, len(ids), 50):
                            batch = ids[i:i+50]
                            try:
                                await bot.client.delete_messages(
                                    chat_id,
                                    batch
                                )
                            except Exception as delete_error:
                                print("history delete error:", delete_error)"""

new = """if ids:
                        for i in range(0, len(ids), 100):
                            batch = ids[i:i+100]
                            try:
                                await bot.client.delete_messages(
                                    chat_id,
                                    batch
                                )
                            except Exception as delete_error:
                                print("history delete error:", delete_error)"""

if old not in text:
    print("❌ بلوک حذف پیدا نشد")
else:
    text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")
    print("✅ حذف تاریخچه 100 تایی فعال شد")
