from pathlib import Path

p = Path("core/bot_working_split_ok.py")
lines = p.read_text(encoding="utf-8").splitlines()

start = None

for i,l in enumerate(lines):
    if '# آزاد کردن کاربر محروم شده' in l:
        start = i
        break

if start is None:
    print("❌ بلاک پیدا نشد")
    exit()

# تا قبل از کنترل فعال بودن گروه
end = start
while end < len(lines) and "# کنترل فعال بودن گروه" not in lines[end]:
    end += 1

for i in range(start, end):
    if lines[i].strip():
        lines[i] = "    " + lines[i]

p.write_text("\n".join(lines)+"\n", encoding="utf-8")

print("✅ ایندنت دستور آزاد اصلاح شد")
