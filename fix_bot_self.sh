python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

old='''            message_text = event.raw_text.strip()'''

new='''            message_text = event.raw_text.strip()

            # جلوگیری از بررسی پیام‌های خود ربات
            if getattr(event, "out", False):
                return'''

if old not in s:
    print("target not found")
else:
    s=s.replace(old,new,1)
    open(p,"w",encoding="utf-8").write(s)
    print("fixed self messages")

PY

python3 -m py_compile main.py && echo "syntax ok"
