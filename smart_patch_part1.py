from pathlib import Path
import shutil
import py_compile

TARGET = Path("handlers/message_handler.py")
BACKUP = TARGET.with_suffix(".py.smart_backup")

def backup():
    shutil.copy2(TARGET, BACKUP)
    print("Backup created:", BACKUP)

def restore():
    if BACKUP.exists():
        shutil.copy2(BACKUP, TARGET)
        print("Restored backup")

def compile_check():
    py_compile.compile(str(TARGET), doraise=True)
    print("Compile OK")

def insert_import(import_line):
    text = TARGET.read_text(encoding="utf-8")
    if import_line in text:
        return
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (lines[i].startswith("from ") or lines[i].startswith("import ")):
        i += 1
    lines.insert(i, import_line)
    TARGET.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    backup()
    insert_import("from modules.security.security_manager import check_security, remove_message")
    compile_check()
