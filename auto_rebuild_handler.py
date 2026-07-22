from pathlib import Path
import ast
import shutil
import subprocess
import re

FILE = Path("handlers/message_handler.py")
BACKUP = Path("handlers/message_handler.py.before_auto_rebuild")

print("🔍 شروع بررسی...")

if not BACKUP.exists():
    shutil.copy(FILE, BACKUP)
    print("✅ بکاپ ساخته شد:", BACKUP)

text = FILE.read_text(encoding="utf-8")
lines = text.splitlines()

def compile_check():
    result = subprocess.run(
        ["python","-m","py_compile",str(FILE)],
        capture_output=True,
        text=True
    )
    return result.returncode, result.stderr

code, err = compile_check()

if code == 0:
    print("✅ فایل سالم است")
    exit()

print("❌ خطای فعلی:")
print(err)

m = re.search(r'line (\d+)', err)
if not m:
    print("❌ شماره خط پیدا نشد")
    exit()

line = int(m.group(1))

print("\n📍 محل خراب:")
for i in range(max(0,line-15), min(len(lines),line+15)):
    print(f"{i+1}: {lines[i]}")

print("\n⚠️ بازسازی خودکار این بخش نیاز به نسخه کامل فایل دارد.")
print("لطفاً کل message_handler.py را ارسال کن.")
