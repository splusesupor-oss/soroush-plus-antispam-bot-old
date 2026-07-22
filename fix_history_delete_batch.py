from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = """                        for msg_id in ids:
                            try:
                                await bot.client.delete_messages(
                                    chat_id,
                                    msg_id
                                )
                            except:
                                pass
"""

new = """                        for i in range(0, len(ids), 100):
                            batch = ids[i:i+100]
                            try:
                                await bot.client.delete_messages(
                                    chat_id,
                                    batch
                                )
                            except Exception as err:
                                print("DELETE BATCH ERROR:", err)
"""

if old in text:
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")
    print("✅ history delete changed to 100 batch")
else:
    print("❌ block not found")
