from pathlib import Path
import ast
import re

file = Path("handlers/message_handler.py")

print("🔍 شروع بررسی:", file)

if not file.exists():
    print("❌ فایل پیدا نشد")
    exit()

text = file.read_text(encoding="utf-8")

# 1) بررسی سینتکس
print("\n=== Syntax ===")
try:
    ast.parse(text)
    print("✅ Syntax سالم است")
except SyntaxError as e:
    print("❌ Syntax Error")
    print("خط:", e.lineno)
    print("مشکل:", e.msg)

# 2) توابع تعریف شده
print("\n=== Functions ===")
try:
    tree = ast.parse(text)
    funcs = [x.name for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) or isinstance(x, ast.AsyncFunctionDef)]
    for f in funcs:
        print("✅", f)
except:
    pass

# 3) توابع مهم استفاده شده ولی تعریف نشده
print("\n=== Missing functions ===")

used = set(re.findall(r'\b([a-zA-Z_]\w*)\s*\(', text))
defined = set(funcs)

important = [
    "remove_admin",
    "add_admin",
    "mute_user",
    "unmute_user",
    "kick_user",
    "warn_user",
    "add_mute",
    "remove_mute",
]

for x in important:
    if x in used and x not in defined and x not in text:
        print("❌ گمشده:", x)

# 4) دستورات ادمین
print("\n=== Admin Commands ===")

commands = [
    "اخطار",
    "سکوت",
    "رفع سکوت",
    "اخراج",
    "برکناری",
    "ادمین",
    "حذف ادمین"
]

for c in commands:
    if c in text:
        print("✅", c)
    else:
        print("❌ نیست:", c)


# 5) بررسی if ادمین
print("\n=== Admin checks ===")

checks = [
    "is_admin",
    "admin",
    "admins",
    "remove_admin",
]

for c in checks:
    print(c, "=", text.count(c))


# 6) پیدا کردن بخش‌های خطرناک
print("\n=== Dangerous blocks ===")

for i,line in enumerate(text.splitlines(),1):
    if "event.reply" in line and ("admin" in line.lower() or "ادمین" in line):
        print("خط",i, line.strip())

    if "if clean_text" in line:
        print("دستور:",i,line.strip())


# 7) بررسی تورفتگی ساده
print("\n=== Indentation scan ===")

try:
    compile(text,"message_handler.py","exec")
    print("✅ تورفتگی OK")
except IndentationError as e:
    print("❌ مشکل تورفتگی")
    print("خط:",e.lineno)
    print(e.msg)


# 8) بکاپ‌ها
print("\n=== Backups ===")

for p in Path("handlers").glob("message_handler*"):
    print(p.name)

print("\n✅ بررسی تمام شد")
