python3 - <<'PY'
p="main.py"

s=open(p,encoding="utf-8").read()

target = '''              # ضد اسپم پیام‌های پشت سرهم
              try:
'''

replace = '''              # ضد اسپم پیام‌های پشت سرهم (موقتاً خاموش)
              if False:
                  try:
'''

if target in s:
    s=s.replace(target, replace, 1)
    print("flood block disabled")
else:
    print("flood target not found")


target2 = '''              # بررسی اسپم تکراری چندخطی داخل یک پیام
              try:
'''

replace2 = '''              # بررسی اسپم تکراری چندخطی داخل یک پیام (موقتاً خاموش)
              if False:
                  try:
'''

if target2 in s:
    s=s.replace(target2, replace2, 1)
    print("multiline spam disabled")
else:
    print("multiline target not found")


open(p,"w",encoding="utf-8").write(s)

PY

python3 -m py_compile main.py && echo "syntax ok"
