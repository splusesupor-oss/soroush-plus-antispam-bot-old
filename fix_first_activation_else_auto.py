from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_first_activation_else_fix.py")

shutil.copy(p,backup)

text=p.read_text(encoding="utf-8")

old='''                    await event.respond(
                        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n"
                        f"مالک گروه: {owner}\\n\\n"
                        f"ادمین های گروه:\\n"
                        + ("\\\\n".join(admins) if admins else "ندارد")
                    )
                    deactivate_group(gid, title)
                    await event.reply(
                        f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                    )'''

new='''                    await event.respond(
                        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n"
                        f"مالک گروه: {owner}\\n\\n"
                        f"ادمین های گروه:\\n"
                        + ("\\\\n".join(admins) if admins else "ندارد")
                    )

                else:
                    deactivate_group(gid, title)
                    await event.reply(
                        f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                    )'''

if old not in text:
    print("❌ block not found")
    exit()

text=text.replace(old,new,1)

p.write_text(text,encoding="utf-8")

print("✅ fixed")
print("backup:",backup)
