from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

backup = p.with_suffix(".before_activation_admin_fix")
shutil.copy(p, backup)

start = text.find("async def get_activation_admin_info")
end = text.find("async def ", start + 10)

if start == -1:
    print("❌ function not found")
    exit()

if end == -1:
    end = len(text)

new_func = r'''
async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            username = getattr(user, "username", None)
            name = username or getattr(user, "first_name", None) or str(getattr(user, "id", ""))

            participant = getattr(user, "participant", None)

            if participant:
                if participant.__class__.__name__.lower().find("creator") >= 0:
                    owner = name

                if participant.__class__.__name__.lower().find("admin") >= 0:
                    admins.append(name)

    except Exception as e:
        return f"خطا: {e}"

    msg = f"مالک گروه: {owner}\n\n"
    msg += "ادمین های گروه:\n"

    if admins:
        for i,a in enumerate(admins,1):
            msg += f"{i}- {a}\n"
    else:
        msg += "ندارد\n"

    return msg

'''

text = text[:start] + new_func + text[end:]

p.write_text(text, encoding="utf-8")

print("✅ activation admin function replaced")
print("backup:", backup)
