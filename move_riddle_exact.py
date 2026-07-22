from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.index("              # RIDDLE_SAFE_INSERTED")
end = s.index("              # ثبت آمار پیام گروه")

block = s[start:end]

# حذف محل قبلی
s = s[:start] + s[end:]

target = '                  chat_id = getattr(chat, "id", 0)'

pos = s.index(target) + len(target)

s = s[:pos] + "\n\n" + block + s[pos:]

p.write_text(s, encoding="utf-8")
print("DONE")
