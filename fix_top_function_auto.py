from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_suffix(".before_top_function_fix")

shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

end = text.find("async def get_group_admins_info")

if end == -1:
    print("❌ end function not found")
    exit()

rest = text[end:]

new = '''async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            participant = getattr(user, "participant", None)

            if participant:
                ptype = type(participant).__name__.lower()

                name = (
                    getattr(user, "username", None)
                    or getattr(user, "first_name", None)
                    or str(getattr(user, "id", ""))
                )

                if "creator" in ptype:
                    owner = name

                elif "admin" in ptype:
                    admins.append(name)

    except Exception as e:
        return f"خطا: {e}"

    msg = f"مالک گروه: {owner}\\n\\n"
    msg += "ادمین های گروه:\\n"

    if admins:
        for i, a in enumerate(admins, 1):
            msg += f"{i}- {a}\\n"
    else:
        msg += "ندارد\\n"

    return msg


'''

p.write_text(new + rest, encoding="utf-8")

print("✅ top function fixed")
print("backup:", backup)
