from pathlib import Path
import shutil

p = Path("handlers/message_handler.py")

backup = p.with_name("message_handler.before_activation_response_fix.py")
shutil.copy(p, backup)

text = p.read_text(encoding="utf-8")

old = '''f"🦊 روباه در گروه «{title}» فعال سازی شد ✅"'''

new = '''f"🦊 روباه در گروه «{title}» فعال سازی شد ✅\\n\\n"
                        f"مالک گروه: {owner}\\n\\n"
                        f"ادمین های گروه:\\n{admins_text}"'''

if old not in text:
    print("❌ activation message not found")
    exit()

text = text.replace(old, new)

# اضافه کردن ساخت اطلاعات قبل از پیام
marker = 'if clean_text == "فعال سازی":'

insert = '''
                    owner, admins = await get_activation_admin_info(bot, gid)
                    admins_text = "\\n".join(admins) if admins else "ندارد"
'''

pos = text.find(marker)

if pos != -1:
    after = text.find("\n", pos)
    text = text[:after+1] + insert + text[after+1:]

p.write_text(text, encoding="utf-8")

print("✅ activation response fixed")
print("backup:", backup)
