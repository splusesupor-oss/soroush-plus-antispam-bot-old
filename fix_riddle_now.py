from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

start = s.find("              # RIDDLE_SAFE_INSERTED")
end = s.find("              # ثبت آمار پیام گروه")

if start == -1 or end == -1:
    print("❌ block not found")
    exit()

block = s[start:end]

# حذف جای قبلی
s = s[:start] + s[end:]

# محل درست: بعد از گرفتن chat_id و user_id و قبل از if await self.check_group_word_commands
pos = s.find("                  if await self.check_group_word_commands(")

if pos == -1:
    print("❌ target not found")
    exit()

s = s[:pos] + "\n" + block + "\n" + s[pos:]

p.write_text(s, encoding="utf-8")

print("✅ riddle moved")
