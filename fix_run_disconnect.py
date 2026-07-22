from pathlib import Path

p = Path("core/bot_working_split_ok.py")
text = p.read_text(encoding="utf-8")

old = '''        print("✅ ربات فعال شد و منتظر پیام است")'''

new = '''        print("✅ ربات فعال شد و منتظر پیام است")

        await self.client.run_until_disconnected()'''

if old not in text:
    print("❌ print فعال پیدا نشد")
    exit()

text = text.replace(old, new, 1)

text = text.replace(
    "\\n        await self.client.run_until_disconnected()\\n",
    "\\n",
    1
)

p.write_text(text, encoding="utf-8")
print("✅ fixed")
