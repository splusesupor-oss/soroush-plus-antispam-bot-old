from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_name("message_handler.before_activation_admin_output_fix.py")

shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

old = '''await event.respond(
                        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅"
                    )'''

new = '''owner, admins = await get_activation_admin_info(bot, gid)

                    await event.respond(
                        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n"
                        f"مالک گروه: {owner}\\n\\n"
                        f"ادمین های گروه:\\n"
                        + ("\\n".join(admins) if admins else "ندارد")
                    )'''

if old in text:
    text=text.replace(old,new,1)
else:
    old2='''await event.respond(
                        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n"
                    )'''
    if old2 in text:
        text=text.replace(old2,new,1)
    else:
        print("❌ activation response not found")
        exit()

p.write_text(text,encoding="utf-8")

print("✅ fixed")
print("backup:",backup)
