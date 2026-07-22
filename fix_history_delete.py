from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old = """                if ids:
                    await bot.client.delete_messages(
                        chat_id,
                        ids
                    )

                print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")
"""

new = """                if ids:
                    for i in range(0, len(ids), 50):
                        batch = ids[i:i+50]
                        try:
                            await bot.client.delete_messages(
                                chat_id,
                                batch
                            )
                        except Exception as delete_error:
                            print("history delete error:", delete_error)

                print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")
"""

if old not in text:
    print("❌ بلوک حذف پیدا نشد")
    exit()

text = text.replace(old, new)

text = text.replace(
'            print("history error:", e)',
''
)

p.write_text(text, encoding="utf-8")

print("✅ history delete fixed")
