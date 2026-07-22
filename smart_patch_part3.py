from pathlib import Path
import py_compile
import shutil

TARGET = Path("handlers/message_handler.py")
BACKUP = TARGET.with_suffix(".py.smart_backup")

def restore():
    if BACKUP.exists():
        shutil.copy2(BACKUP, TARGET)
        print("✅ backup restored")

try:
    py_compile.compile(str(TARGET), doraise=True)
    print("✅ compile ok")
except Exception as e:
    print("❌ compile error")
    print(e)
    restore()
    raise SystemExit

text = TARGET.read_text(encoding="utf-8")

errors = []

if "check_security(" not in text:
    errors.append("check_security")

if "remove_message(" not in text:
    errors.append("remove_message")

if "from modules.security.security_manager import check_security, remove_message" not in text:
    errors.append("import")

if errors:
    print("❌ missing:", ", ".join(errors))
else:
    print("✅ security system installed successfully")

print("-----------")
print("Verification finished")
