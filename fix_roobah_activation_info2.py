from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_roobah_info2")
backup.write_text(text,encoding="utf-8")

helper='''

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

    msg = f"👑 مالک گروه : {owner}\\n\\n"
    msg += "🛡️ ادمین های گروه:\\n"

    if admins:
        for i,a in enumerate(admins,1):
            msg += f"{i}- {a}\\n"
    else:
        msg += "ندارد\\n"

    return msg

'''

if "async def get_activation_admin_info" not in text:
    text=helper+text


old='''f"🦊 روباه در گروه «{title}» فعال سازی شد ✅"'''

new='''f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n{await get_activation_admin_info(bot, chat_id)}"'''

count=text.count(old)

if count:
    text=text.replace(old,new)
    p.write_text(text,encoding="utf-8")
    print("✅ activation message updated:",count)
    print("backup:",backup)
else:
    print("❌ exact message not found")

