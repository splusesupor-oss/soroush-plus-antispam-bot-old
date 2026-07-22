from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

target = "is_spam, reason = bot.detector.is_spam(message_text, chat_id)"

idx = -1
for i, line in enumerate(lines):
    if target in line:
        idx = i
        break

if idx == -1:
    print("❌ محل detector پیدا نشد")
    exit()

# جلوگیری از دوباره اضافه شدن
if "ADMIN BYPASS BEFORE DETECTOR" in "\n".join(lines[max(0,idx-20):idx]):
    print("⚠️ قبلا اضافه شده")
    exit()

indent = lines[idx][:len(lines[idx])-len(lines[idx].lstrip())]

block = [
    indent + "# ADMIN BYPASS BEFORE DETECTOR",
    indent + "try:",
    indent + "    from modules.admin_storage import is_admin",
    indent + "    if is_admin(chat_id, username):",
    indent + "        print(f'✅ ADMIN BYPASS FILTER: {username}')",
    indent + "        is_spam = False",
    indent + "        reason = ''",
    indent + "        return",
    indent + "except Exception as e:",
    indent + "    print('ADMIN CHECK ERROR:', e)",
    ""
]

lines[idx:idx] = block

p.write_text("\n".join(lines)+"\n", encoding="utf-8")

print("✅ محافظ ادمین قبل detector اضافه شد")
