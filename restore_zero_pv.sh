python3 - <<'PY'
from pathlib import Path

src = Path("main.py.backup_before_separate_filter").read_text()

start = src.find("              # پیوی فقط دستور صفر کردن تخلف")
end = src.find("            # فعال و غیرفعال کردن گروه توسط مالک اصلی", start)

if start == -1 or end == -1:
    print("marker not found")
    exit()

block = src[start:end]

dst = Path("main.py").read_text()

# اگر بخش مشابه وجود دارد حذفش کن
s2 = dst.find("              # پیوی فقط دستور صفر کردن تخلف")
e2 = dst.find("            # فعال و غیرفعال کردن گروه توسط مالک اصلی", s2)

if s2 != -1 and e2 != -1:
    dst = dst[:s2] + dst[e2:]

# قرار دادن قبل از فعال سازی
pos = dst.find("            # فعال و غیرفعال کردن گروه توسط مالک اصلی")

dst = dst[:pos] + block + "\n" + dst[pos:]

Path("main.py").write_text(dst)

print("zero pv restored")
PY

python3 -m py_compile main.py && echo "syntax ok"
