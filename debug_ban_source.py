from pathlib import Path

p = Path("handlers/message_handler.py")
text = p.read_text(encoding="utf-8")

old1 = """await bot.admin_actions.ban_user(
                    chat_id,
                    user_id
                )"""

new1 = """print(f"🚨 BAN FROM HISTORY | chat={chat_id} user={user_id}")
                await bot.admin_actions.ban_user(
                    chat_id,
                    user_id
                )"""

if old1 in text:
    text = text.replace(old1, new1, 1)

old2 = """await bot.admin_actions.ban_user(chat_id, user_id)"""

new2 = """print(f"🚨 BAN FROM REPEAT_SPAM | chat={chat_id} user={user_id}")
                        await bot.admin_actions.ban_user(chat_id, user_id)"""

if old2 in text:
    text = text.replace(old2, new2, 1)

p.write_text(text, encoding="utf-8")

p = Path("modules/admin_actions.py")
text = p.read_text(encoding="utf-8")

marker = "async def ban_user(self, chat_id, user_id) -> bool:"
if marker in text and "ban_user CALLED" not in text:
    text = text.replace(
        marker,
        marker + """
        import traceback
        print("="*60)
        print("ban_user CALLED")
        print(f"chat={chat_id} user={user_id}")
        traceback.print_stack(limit=8)
        print("="*60)
""",
        1,
    )

p.write_text(text, encoding="utf-8")

print("✅ Debug installed")
