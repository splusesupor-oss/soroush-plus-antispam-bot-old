from pathlib import Path
import re

files = [
    Path("handlers/message_handler.py")
]

for p in files:
    s = p.read_text(encoding="utf-8")

    # حذف import محلی که باعث local variable شدن is_admin می‌شود
    old = re.findall(
        r'\n[ \t]+from modules\.admin_storage import is_admin\n',
        s
    )

    if old:
        s = re.sub(
            r'\n[ \t]+from modules\.admin_storage import is_admin\n',
            '\n',
            s
        )
        print("✅ import خراب is_admin حذف شد")
    else:
        print("ℹ️ import محلی پیدا نشد")

    # اگر import سراسری وجود ندارد، اضافه کن
    if "from modules.admin_storage import is_admin" not in s:
        pos = s.find("\n")
        s = s[:pos+1] + "from modules.admin_storage import is_admin\n" + s[pos+1:]
        print("✅ import سراسری is_admin اضافه شد")

    p.write_text(s, encoding="utf-8")

print("✅ اصلاح کامل شد")
