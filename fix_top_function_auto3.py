from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = Path("handlers/message_handler.before_top_fix3.py")

shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

start = text.find("async def get_activation_admin_info")

if start == -1:
    print("❌ function not found")
    exit()

end = text.find("async def ", start + 10)

if end == -1:
    print("❌ next function not found")
    exit()

new_func = '''async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            name = (
                getattr(user, "username", None)
                or getattr(user, "first_name", None)
                or str(getattr(user, "id", ""))
            )

            participant = getattr(user, "participant", None)

            if participant:
                kind = type(participant).__name__.lower()

                if "creator" in kind:
                    owner = name
                elif "admin" in kind:
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

p.write_text(
    text[:start] + new_func + text[end:],
    encoding="utf-8"
)

print("✅ function replaced")
print("backup:", backup)
