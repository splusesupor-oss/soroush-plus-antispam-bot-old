from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.before_activation_line_fix.py")

shutil.copy(p,backup)

lines=p.read_text(encoding="utf-8").splitlines()

start=None
for i,l in enumerate(lines):
    if i>640 and 'if clean_text == "فعال سازی":' in l:
        start=i
        break

if start is None:
    print("❌ not found")
    exit()

end=start
while end < len(lines):
    if 'deactivate_group' in lines[end]:
        break
    end+=1

block=[
'                if clean_text == "فعال سازی":',
'                    activate_group(gid, title)',
'',
'                    owner, admins = await get_activation_admin_info(bot, gid)',
'',
'                    await event.respond(',
'                        f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n"',
'                        f"مالک گروه: {owner}\\n\\n"',
'                        f"ادمین های گروه:\\n"',
'                        + ("\\n".join(admins) if admins else "ندارد")',
'                    )'
]

lines[start:end]=block

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ fixed")
print("backup:",backup)
