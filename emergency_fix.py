from pathlib import Path
import shutil

p = Path("test_main.py")

shutil.copy(p, "test_main.py.before_emergency_fix")

lines = p.read_text(encoding="utf-8").splitlines()

# اصلاح indent خط if is_spam
for i,l in enumerate(lines):
    if l.strip() == "if is_spam:":
        # اگر خیلی کم فاصله دارد
        lines[i] = "            if is_spam:"
        print("fixed if is_spam line", i+1)

# حذف import محلی خراب is_admin داخل تابع
for i,l in enumerate(lines):
    if "from modules.admin_manager import is_admin" in l:
        lines[i] = "                pass  # removed bad local import"
        print("removed local is_admin import", i+1)

# اضافه کردن import functions در ابتدای فایل اگر نیست
text="\n".join(lines)

if "from splusthon.tl import functions" not in text:
    if "from splusthon import types" in text:
        text=text.replace(
            "from splusthon import types",
            "from splusthon import types\nfrom splusthon.tl import functions",
            1
        )
        print("added functions import")

p.write_text(text+"\n",encoding="utf-8")

print("✅ emergency fix done")
