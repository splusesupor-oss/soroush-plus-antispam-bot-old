from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_admin_info_real_fix.py")
shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

start=text.find("async def get_activation_admin_info")
end=text.find("\nasync def ", start+10)

if end == -1:
    end=len(text)

new_func=r'''async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            username = getattr(user, "username", None)
            name = (
                "@" + username if username
                else getattr(user, "first_name", None)
                or str(getattr(user, "id", ""))
            )

            if getattr(user, "is_creator", False):
                owner = name
            elif getattr(user, "is_admin", False):
                admins.append(name)

            participant = getattr(user, "participant", None)
            if participant:
                kind = participant.__class__.__name__
                if "Creator" in kind:
                    owner = name
                elif "Admin" in kind:
                    admins.append(name)

    except Exception as e:
        print("ADMIN INFO ERROR:", e)

    return owner, admins
'''

p.write_text(text[:start]+new_func+text[end:],encoding="utf-8")

print("✅ admin info fixed")
print("backup:",backup)
