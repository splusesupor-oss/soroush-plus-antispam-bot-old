from pathlib import Path
import re
import shutil

FILE = Path("handlers/message_handler.py")

print("🔧 شروع تعمیر خودکار دسترسی ادمین")

if not FILE.exists():
    print("❌ فایل پیدا نشد")
    exit()

backup = FILE.with_suffix(".before_admin_repair.py")
shutil.copy(FILE, backup)

text = FILE.read_text(encoding="utf-8")

# import admin_storage
needed = "from modules.admin_storage import is_admin, add_admin, remove_admin"

if "from modules.admin_storage import" not in text:
    text = needed + "\n" + text
    print("✅ import admin_storage اضافه شد")

else:
    line = re.search(r"from modules\.admin_storage import .*", text)
    if line:
        old=line.group(0)

        funcs=set()

        for x in ["is_admin","add_admin","remove_admin"]:
            if x in old:
                funcs.add(x)

        for x in ["is_admin","add_admin","remove_admin"]:
            funcs.add(x)

        new="from modules.admin_storage import " + ", ".join(sorted(funcs))

        text=text.replace(old,new)
        print("✅ import ادمین اصلاح شد")


# check_answer
if "check_answer" not in text.split("\n")[0:20]:
    text=text.replace(
        "from modules.riddles import new_riddle",
        "from modules.riddles import new_riddle, check_answer"
    )
    print("✅ check_answer اضافه شد")


# new_riddle
if "new_riddle" not in text.split("\n")[0:20]:
    text=text.replace(
        "from modules.riddles import check_answer",
        "from modules.riddles import new_riddle, check_answer"
    )
    print("✅ new_riddle اضافه شد")


# add_message
if "add_message" not in text.split("\n")[0:30]:
    text=text.replace(
        "from modules.group_stats import",
        "from modules.group_stats import add_message,",
        1
    )
    print("✅ add_message اضافه شد")


# UserTracker
if "UserTracker" in text and "from modules.user_tracker import" not in text:
    text="from modules.user_tracker import UserTracker\n"+text
    print("✅ UserTracker اضافه شد")


FILE.write_text(text,encoding="utf-8")


print("\n🧪 تست syntax")

import py_compile

try:
    py_compile.compile(str(FILE),doraise=True)
    print("✅ syntax سالم")
except Exception as e:
    print("❌ خطای syntax:")
    print(e)


print("\n📌 بکاپ:")
print(backup)

print("✅ تمام شد")
