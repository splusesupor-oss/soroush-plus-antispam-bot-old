from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find("              # RIDDLE_SAFE_INSERTED")
end = s.find("              # ثبت آمار پیام گروه")

if start == -1 or end == -1:
    print("❌ block not found")
    exit()

block = s[start:end]

# حذف از جای فعلی
s = s[:start] + s[end:]

# پیدا کردن قبل از بازی جرعت
target = '              # بازی جرعت حقیقت'

pos = s.find(target)

if pos == -1:
    print("❌ jorat marker not found")
    exit()

# گذاشتن بعد از clean_text داخل همان بخش
s = s[:pos] + block + "\n" + s[pos:]

p.write_text(s, encoding="utf-8")
print("✅ moved")
