from pathlib import Path
import shutil

p = Path("main.py")
backup = Path("main.py.before_riddle_fix2")

shutil.copy2(p, backup)

s = p.read_text(encoding="utf-8")

start = s.find("# RIDDLE_SAFE_INSERTED")
if start == -1:
    print("❌ riddle marker not found")
    exit()

end = s.find("# ثبت آمار پیام گروه", start)
if end == -1:
    print("❌ end marker not found")
    exit()

block = s[start:end]

# حذف بلوک فعلی
s = s[:start] + s[end:]

target = 'chat_id = getattr(chat, "id", 0)'

pos = s.find(target)

if pos == -1:
    print("❌ chat_id not found")
    exit()

# رفتن انتهای همان خط
pos = s.find("\n", pos) + 1

# اضافه کردن بعد از ساخت chat_id
s = s[:pos] + "\n" + block + s[pos:]

p.write_text(s, encoding="utf-8")

print("✅ moved after chat_id")
print("backup:", backup)
