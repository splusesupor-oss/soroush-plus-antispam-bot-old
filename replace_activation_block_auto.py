from pathlib import Path
import shutil
import re

p = Path("handlers/message_handler.py")
backup = p.with_name("message_handler.before_activation_block_replace.py")

shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

pattern = r'if clean_text == "فعال سازی":.*?await event\.respond\((.*?)\)'

match = re.search(pattern, text, re.S)

if not match:
    print("❌ block not found")
    exit()

new = '''if clean_text == "فعال سازی":
                    activate_group(gid, title)

                    owner, admins = await get_activation_admin_info(bot, gid)

                    await event.respond(
                        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n"
                        f"مالک گروه: {owner}\\n\\n"
                        f"ادمین های گروه:\\n"
                        + ("\\n".join(admins) if admins else "ندارد")
                    )'''

text = text[:match.start()] + new + text[match.end():]

p.write_text(text, encoding="utf-8")

print("✅ activation block replaced")
print("backup:", backup)
