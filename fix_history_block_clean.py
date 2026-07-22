from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

start = text.find("if is_repeat(chat_id, user_id, message_text):")
end = text.find("clear_user(chat_id, user_id)")

if start == -1 or end == -1:
    print("❌ بلوک پیدا نشد")
    exit()

new = """if is_repeat(chat_id, user_id, message_text):
                            print("🚨 HISTORY REPEAT BAN:", user_id)

                            ids = get_message_ids(chat_id, user_id)

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

                            print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")
                            await bot.admin_actions.ban_user(
                                chat_id,
                                user_id
                            )

"""

text = text[:start] + new + text[end:]

p.write_text(text, encoding="utf-8")
print("✅ history block restored")
