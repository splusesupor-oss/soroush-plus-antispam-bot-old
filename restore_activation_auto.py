from pathlib import Path
import re
import shutil

src = Path("claude_files/message_handler.py")
dst = Path("handlers/message_handler.py")

backup = Path("handlers/message_handler.before_activation_restore.py")
shutil.copy(dst, backup)

s = src.read_text(encoding="utf-8")

m = re.search(
    r"# فعال و غیرفعال کردن گروه توسط مالک اصلی.*?(?=\n\s*if clean_text in |\Z)",
    s,
    re.S
)

if not m:
    print("❌ block not found")
    exit()

block = m.group(0)

t = dst.read_text(encoding="utf-8")

# حذف نسخه‌های خراب قبلی
t = re.sub(
    r"# فعال و غیرفعال کردن گروه توسط مالک اصلی.*?(?=\n\s*if clean_text in |\Z)",
    "",
    t,
    flags=re.S
)

# اضافه قبل از پایان handle_new_message
pos = t.find("\n    async def handle_admin_commands")

if pos == -1:
    pos = len(t)

t = t[:pos] + "\n\n    " + block.replace("\n", "\n    ") + "\n" + t[pos:]

dst.write_text(t, encoding="utf-8")

print("✅ activation restored")
print("backup:", backup)
