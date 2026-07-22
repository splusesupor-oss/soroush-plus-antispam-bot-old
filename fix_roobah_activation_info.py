from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_roobah_info")
backup.write_text(text,encoding="utf-8")

if "async def get_activation_admin_info" not in text:
    helper = r'''

async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for u in bot.client.iter_participants(chat_id):
            if getattr(u, "is_creator", False):
                owner = getattr(u, "username", None) or str(u.id)

            if getattr(u, "admin_rights", None):
                admins.append(
                    getattr(u, "username", None) or str(u.id)
                )

    except Exception as e:
        return f"خطا: {e}"

    msg = "👑 مالک گروه :\n"
    msg += f"{owner}\n\n"
    msg += "🛡️ ادمین های گروه:\n"

    if admins:
        for i,a in enumerate(admins,1):
            msg += f"{i}- {a}\n"
    else:
        msg += "ندارد\n"

    return msg

'''
    text = helper + "\n" + text


old='''🦊 روباه در گروه «{group_name}» فعال سازی شد ✅'''

new='''🦊 روباه در گروه «{group_name}» فعال سازی شد ✅

{admin_info}'''

if old in text:
    text=text.replace(old,new,1)

    text=text.replace(
        'await event.respond(message)',
        'admin_info = await get_activation_admin_info(bot, chat_id)\\n                await event.respond(message)',
        1
    )

    p.write_text(text,encoding="utf-8")
    print("✅ activation owner/admin info added")
    print("backup:",backup)

else:
    print("❌ activation message not found")
