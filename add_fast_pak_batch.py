from pathlib import Path
import re

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_fast_pak")
backup.write_text(text,encoding="utf-8")

old='''if clean_text.startswith("پاک "):'''

new='''if clean_text.startswith("پاک "):
            try:
                parts = clean_text.split()
                count = int(parts[1])

                if count > 0:
                    print(f"🧹 FAST DELETE REQUEST: {count}")

                    msgs = []
                    async for m in bot.client.iter_messages(
                        chat_id,
                        limit=count
                    ):
                        msgs.append(m.id)

                    for i in range(0, len(msgs), 100):
                        batch = msgs[i:i+100]
                        try:
                            await bot.client.delete_messages(
                                chat_id,
                                batch
                            )
                            import asyncio
                            await asyncio.sleep(0.2)
                        except Exception as err:
                            print("DELETE BATCH ERROR:", err)

                    await event.respond(
                        f"🧹 {len(msgs)} پیام پاک شد"
                    )

                    return

            except Exception as err:
                print("FAST PAK ERROR:", err)

            '''

if old in text:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ fast پاک batch added")
    print("backup:",backup)
else:
    print("❌ marker not found")
