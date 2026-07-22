from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = """try:
                                            await bot.client.delete_messages(
                                                chat_id,
                                                batch
                                            )
                                        except Exception as delete_error:
                                            print("fast history delete error:", delete_error)"""

new = """try:
                                            for msg_id in batch:
                                                await bot.client.delete_messages(
                                                    chat_id,
                                                    msg_id
                                                )
                                        except Exception as delete_error:
                                            print("fast history delete error:", delete_error)"""

if old not in text:
    print("❌ بلوک پیدا نشد")
else:
    text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")
    print("✅ حذف پیام‌ها یکی یکی فعال شد")

