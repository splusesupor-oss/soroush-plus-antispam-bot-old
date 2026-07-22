from pathlib import Path
import shutil

p = Path("main.py")
shutil.copy2(p, "main.py.before_riddle_line_move")

lines = p.read_text(encoding="utf-8").splitlines(True)

start = None
end = None

for i, line in enumerate(lines):
    if "if clean_text == \"چیستان\":" in line:
        start = i - 1
        while start > 0 and "# RIDDLE" not in lines[start]:
            start -= 1
        break

if start is None:
    print("❌ start not found")
    exit()

for i in range(start, len(lines)):
    if "# ثبت آمار پیام گروه" in lines[i]:
        end = i
        break

if end is None:
    print("❌ end not found")
    exit()

block = lines[start:end]

del lines[start:end]

# پیدا کردن انتهای فیلتر کلمات
insert = None
for i, line in enumerate(lines):
    if 'f"خطای فیلتر گروه: {e}"' in line:
        for j in range(i, len(lines)):
            if lines[j].strip() == ")":
                insert = j + 1
                break
        break

if insert is None:
    print("❌ insert point not found")
    exit()

lines[insert:insert] = ["\n"] + block

p.write_text("".join(lines), encoding="utf-8")

print("✅ moved by line")
