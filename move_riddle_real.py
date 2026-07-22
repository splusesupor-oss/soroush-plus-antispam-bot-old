from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find('              if clean_text == "چیستان":')
if start == -1:
    print("❌ chiestan not found")
    exit()

end = s.find('              # ثبت آمار پیام گروه', start)
if end == -1:
    print("❌ end not found")
    exit()

block = s[start:end]

# حذف چیستان فعلی
s = s[:start] + s[end:]

target = '                  chat_id = getattr(chat, "id", 0)'
pos = s.find(target)

if pos == -1:
    print("❌ chat_id not found")
    exit()

pos += len(target)

s = s[:pos] + "\n\n" + block + s[pos:]

p.write_text(s, encoding="utf-8")

print("✅ moved")
