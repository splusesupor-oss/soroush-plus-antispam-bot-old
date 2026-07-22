from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")
backup = p.with_name("message_handler.before_unpack_fix.py")
shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

text = text.replace(
'owner, admins = await get_activation_admin_info(bot, gid)',
'admin_info = await get_activation_admin_info(bot, gid)\n                    owner = admin_info[0]\n                    admins = admin_info[1] if len(admin_info) > 1 else []'
)

p.write_text(text, encoding="utf-8")

print("✅ unpack fixed")
print("backup:", backup)
