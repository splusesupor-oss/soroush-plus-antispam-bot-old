from pathlib import Path

p = Path("handlers/message_handler.py")
lines = p.read_text(encoding="utf-8").splitlines()

target = "is_spam, reason = bot.detector.is_spam(message_text, chat_id)"

idx = -1
for i,line in enumerate(lines):
    if target in line:
        idx = i
        break

if idx == -1:
    print("❌ detector پیدا نشد")
    exit()

text="\n".join(lines[max(0,idx-40):idx])

if "FORWARD BYPASS BEFORE DETECTOR" in text:
    print("⚠️ قبلاً اضافه شده")
    exit()

indent = lines[idx][:len(lines[idx])-len(lines[idx].lstrip())]

block = [
    indent + "# FORWARD BYPASS BEFORE DETECTOR",
    indent + "try:",
    indent + "    if getattr(event.message, 'fwd_from', None):",
    indent + "        print('✅ FORWARD BYPASS')",
    indent + "        is_spam = False",
    indent + "        reason = ''",
    indent + "        return",
    indent + "except Exception as e:",
    indent + "    print('FORWARD CHECK ERROR:', e)",
    ""
]

lines[idx:idx]=block

p.write_text("\n".join(lines)+"\n",encoding="utf-8")

print("✅ محافظ فوروارد قبل فیلتر اضافه شد")
