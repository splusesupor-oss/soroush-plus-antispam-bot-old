from pathlib import Path

safe = Path("handlers/message_handler.py")
bad = Path("handlers/message_handler.py.BROKEN_FINAL")

s = safe.read_text(encoding="utf-8")
b = bad.read_text(encoding="utf-8")

# اضافه کردن import
imp = "from modules.spam_history import save_history_message, is_repeat, get_message_ids, clear_user"

if "from modules.spam_history import" not in s:
    lines = s.splitlines()
    for i,l in enumerate(lines):
        if "from modules." in l:
            lines.insert(i+1, imp)
            break
    s = "\n".join(lines)

# گرفتن بخش تاریخچه از فایل خراب
start = b.find("        # ذخیره تاریخچه پیام برای ضد تکرار")
end = b.find("        # جستجوی وب")

if start != -1 and end != -1:
    block = b[start:end]

    if "# ذخیره تاریخچه پیام برای ضد تکرار" not in s:
        pos = s.find("        # جستجوی وب")
        if pos != -1:
            s = s[:pos] + block + "\n" + s[pos:]

# گرفتن فیلتر جستجو
start2 = b.find("            # فیلتر مطالب غیرمجاز جستجو")
end2 = b.find("            if query:")

if start2 != -1 and end2 != -1:
    block2 = b[start2:end2]

    if "blocked_search_words" not in s:
        pos2 = s.find("            if query:")
        if pos2 != -1:
            s = s[:pos2] + block2 + "\n" + s[pos2:]

safe.write_text(s, encoding="utf-8")

print("✅ merge finished")
