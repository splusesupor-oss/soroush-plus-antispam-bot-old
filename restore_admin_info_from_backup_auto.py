from pathlib import Path
import shutil

target = Path("handlers/message_handler.py")

backup = Path("handlers/message_handler.before_clean_restore.py")

if not backup.exists():
    print("❌ backup not found")
    exit()

src = backup.read_text(encoding="utf-8")

start = src.find("async def get_activation_admin_info")
end = src.find("\nasync def ", start + 10)

if start == -1:
    print("❌ function not found in backup")
    exit()

if end == -1:
    end = len(src)

func = src[start:end]

old = target.read_text(encoding="utf-8")

target_backup = target.with_name("message_handler.before_admin_restore2.py")
shutil.copy(target, target_backup)

# حذف نسخه‌های خراب احتمالی
s = old.find("async def get_activation_admin_info")
if s != -1:
    e = old.find("\nasync def ", s + 10)
    if e == -1:
        e = len(old)
    old = old[:s] + old[e:]

target.write_text(func + "\n\n" + old, encoding="utf-8")

print("✅ admin info restored")
print("backup:", target_backup)
