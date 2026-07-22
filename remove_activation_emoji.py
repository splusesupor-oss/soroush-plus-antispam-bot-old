from pathlib import Path

p=Path("handlers/message_handler.py")
text=p.read_text(encoding="utf-8")

text=text.replace("👑 مالک گروه :", "مالک گروه:")
text=text.replace("🛡️ ادمین های گروه:", "ادمین های گروه:")

p.write_text(text,encoding="utf-8")

print("✅ activation emojis removed")
