from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

backup=Path("handlers/message_handler.before_owner_admins")
backup.write_text(text,encoding="utf-8")

old='''روباه در گروه'''

new='''روباه در گروه'''

# اضافه کردن تابع کمکی قبل از اولین استفاده
insert='''

async def get_group_admins_info(bot, chat_id):
    try:
        admins = []
        owner = "نامشخص"

        async for user in bot.client.iter_participants(
            chat_id,
            filter=None
        ):
            if getattr(user, "admin_rights", None):
                admins.append(
                    getattr(user, "username", None)
                    or str(user.id)
                )

            if getattr(user, "is_creator", False):
                owner = (
                    getattr(user, "username", None)
                    or str(user.id)
                )

        txt = f"مالک گروه :\\n{owner}\\n\\nادمین های گروه:\\n"

        for i, a in enumerate(admins,1):
            txt += f"{i} - {a}\\n"

        return txt

    except Exception as e:
        return f"خطا در دریافت مدیران: {e}"

'''

if "async def get_group_admins_info" not in text:
    text=insert+text


# پیدا کردن پیام فعال شدن روباه
target='''روباه در گروه'''

if target in text:
    text=text.replace(
        target,
        target,
        1
    )

    p.write_text(text,encoding="utf-8")
    print("✅ helper added")
    print("backup:",backup)
else:
    print("❌ activation text not found")
