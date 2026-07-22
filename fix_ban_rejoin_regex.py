import re
import shutil

file = "main.py"
backup = "main.py.before_ban_rejoin_regex_fix"

shutil.copy2(file, backup)
print("✅ بکاپ:", backup)

with open(file, "r", encoding="utf-8") as f:
    data = f.read()

pattern = r'await self\.client\.kick_participant\(\s*chat_id,\s*user\s*\)'

replacement = '''await self.client.edit_permissions(
                    chat_id,
                    user,
                    view_messages=False
                )'''

new_data, count = re.subn(pattern, replacement, data, count=1)

if count:
    with open(file, "w", encoding="utf-8") as f:
        f.write(new_data)

    print("✅ تغییر انجام شد")
else:
    print("❌ بخش موردنظر پیدا نشد")

