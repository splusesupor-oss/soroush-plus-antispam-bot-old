from pathlib import Path
import shutil

p = Path("main.py")

shutil.copy2(p, "main.py.before_riddle_import_fix")

s = p.read_text(encoding="utf-8")

line = "from modules.riddles import new_riddle\n"

if line in s:
    print("⚠️ already exists")
    exit()

target = "from modules.group_banned_words_control import enable, disable\n"

if target not in s:
    print("❌ import area not found")
    exit()

s = s.replace(target, target + line, 1)

p.write_text(s, encoding="utf-8")

print("✅ riddle import added")
