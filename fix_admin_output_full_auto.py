from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_name("message_handler.before_admin_output_full.py")
shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

start = text.find("async def get_activation_admin_info")
end = text.find("\nasync def ", start + 10)

if start == -1:
    print("❌ function not found")
    exit()

if end == -1:
    end = len(text)

new = r'''
async def get_activation_admin_info(bot, chat_id):
    owner = "نامشخص"
    admins = []

    try:
        async for user in bot.client.iter_participants(chat_id, limit=200):
            username = getattr(user, "username", None)
            first = getattr(user, "first_name", None)
            last = getattr(user, "last_name", None)

            name = ""

            if username:
                name = "@" + username
            elif first:
                name = first
                if last:
                    name += " " + last
            else:
                name = str(getattr(user, "id", ""))

            participant = getattr(user, "participant", None)

            if participant:
                kind = participant.__class__.__name__

                if "Creator" in kind or "Owner" in kind:
                    owner = name

                elif "Admin" in kind:
                    admins.append(name)

    except Exception as e:
        print("ADMIN INFO ERROR:", e)

    return owner, admins
'''

text = text[:start] + new + text[end:]

p.write_text(text, encoding="utf-8")

print("✅ full admin output fixed")
print("backup:", backup)
