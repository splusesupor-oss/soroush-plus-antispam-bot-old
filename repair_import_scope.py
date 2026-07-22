from pathlib import Path

p = Path("test_main.py")
s = p.read_text(encoding="utf-8")

# حذف import های محلی خراب
s = s.replace(
"from modules.admin_manager import is_admin\n",
""
)

# اضافه کردن import درست اگر وجود ندارد
if "from modules.admin_storage import is_admin, add_admin, remove_admin" not in s:
    s = "from modules.admin_storage import is_admin, add_admin, remove_admin\n" + s

# مشکل functions
if "from splusthon.tl import functions" not in s:
    if "from splusthon import types" in s:
        s = s.replace(
            "from splusthon import types",
            "from splusthon import types\nfrom splusthon.tl import functions",
            1
        )

p.write_text(s, encoding="utf-8")
print("✅ import scope ها اصلاح شد")
