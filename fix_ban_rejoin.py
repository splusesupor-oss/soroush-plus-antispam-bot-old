import shutil
import re
from datetime import datetime

file = "main.py"

backup = f"main.py.before_ban_rejoin_fix"

print("🔎 بررسی main.py ...")

try:
    with open(file, "r", encoding="utf-8") as f:
        data = f.read()
except Exception as e:
    print("❌ خطا در خواندن فایل:", e)
    exit()

# بکاپ
shutil.copy2(file, backup)
print("✅ بکاپ ساخته شد:", backup)

old = """await self.client.kick_participant(
    chat_id,
    user
)"""

new = """await self.client.edit_permissions(
    chat_id,
    user,
    view_messages=False
)"""

if old in data:
    data = data.replace(old, new, 1)

    with open(file, "w", encoding="utf-8") as f:
        f.write(data)

    print("✅ kick_participant در بخش بن ورود با edit_permissions جایگزین شد")

else:
    print("⚠️ الگوی دقیق پیدا نشد")
    print("احتمالاً فاصله‌ها یا ساختار کد فرق دارد")

print("تمام شد")
