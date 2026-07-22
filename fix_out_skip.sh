python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''            message_text = getattr(event.message, "message", "") or ""'''

new='''            # رد کردن پیام‌های خود ربات
            if getattr(event, "out", False):
                return

            message_text = getattr(event.message, "message", "") or ""'''

if old not in s:
    print("target not found")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("fixed")

PY

python3 -m py_compile main.py && echo "syntax ok"
