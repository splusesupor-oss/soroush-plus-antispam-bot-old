#!/data/data/com.termux/files/usr/bin/bash

python3 - <<'PY'
from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

old = '''            # بررسی کلمات فیلتر شده گروه
            group_word_spam = False
            group_word_reason = None
'''

new = '''            # بررسی کلمات فیلتر شده گروه
            group_word_spam = False
            group_word_reason = None

            # دستورات مدیریت کلمات نباید توسط فیلتر گرفته شوند
            word_admin_commands = (
                "فیلتر کلمه",
                "حذف کلمه",
                "افزودن کلمه",
                "ثبت کلمه",
                "لیست کلمات",
                "پاک کردن کلمات"
            )

            if any(message_text.startswith(x) for x in word_admin_commands):
                group_word_spam = False
'''

if old in s:
    s = s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("WORD COMMAND BYPASS OK")
else:
    print("MARKER NOT FOUND")

PY

python3 -m py_compile main.py && echo "MAIN OK"
