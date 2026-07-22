from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

start=text.find("async def get_activation_admin_info")
end=text.find("async def get_group_admins_info")

if start == -1 or end == -1:
    print("❌ function block not found")
    exit()

new_func='''async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for p in bot.client.iter_participants(chat_id):
            name = getattr(p, "username", None) or str(getattr(p, "id", ""))

            if getattr(p, "participant", None):
                part = p.participant

                if getattr(part, "is_creator", False):
                    owner = name

                if getattr(part, "admin_rights", None):
                    admins.append(name)

        msg = f"مالک گروه: {owner}\\n\\n"
        msg += "ادمین های گروه:\\n"

        if admins:
            for i,a in enumerate(admins,1):
                msg += f"{i}- {a}\\n"
        else:
            msg += "ندارد\\n"

        return msg

    except Exception as e:
        return f"خطا: {e}"


'''

text=text[:start]+new_func+text[end:]

p.write_text(text,encoding="utf-8")

print("✅ activation admin function fixed")
