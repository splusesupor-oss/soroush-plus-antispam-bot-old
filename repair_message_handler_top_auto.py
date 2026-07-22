from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = Path("handlers/message_handler.before_repair_top.py")

shutil.copy(p, backup)

lines = p.read_text(encoding="utf-8").splitlines()

# حذف بخش خراب ابتدای فایل تا قبل از اولین هندلر اصلی
idx = -1

for i,line in enumerate(lines):
    if line.startswith("async def handle_") or line.startswith("async def new_"):
        idx = i
        break

if idx == -1:
    for i,line in enumerate(lines):
        if "event" in line and "chat_id" in line:
            idx = i
            break

if idx == -1:
    print("❌ main handler not found")
    exit()

func = '''async def get_activation_admin_info(bot, chat_id):
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
                t = type(participant).__name__.lower()

                if "creator" in t:
                    owner = name
                elif "admin" in t:
                    admins.append(name)

    except Exception as e:
        return f"خطا: {e}"

    msg = f"مالک گروه: {owner}\\n\\nادمین های گروه:\\n"

    if admins:
        for i,a in enumerate(admins,1):
            msg += f"{i}- {a}\\n"
    else:
        msg += "ندارد\\n"

    return msg


'''

p.write_text(
    func + "\n".join(lines[idx:]) + "\n",
    encoding="utf-8"
)

print("✅ repaired")
print("backup:", backup)
