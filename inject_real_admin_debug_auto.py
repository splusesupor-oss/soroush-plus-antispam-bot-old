from pathlib import Path

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

if "PART DEBUG REAL" in text:
    print("already installed")
    exit()

old = 'async for user in bot.client.iter_participants(chat_id, limit=200):'

new = '''async for user in bot.client.iter_participants(chat_id, limit=200):
            print("PART DEBUG REAL:", repr(user), type(user))
'''

if old not in text:
    print("❌ iter_participants not found")
else:
    text=text.replace(old,new,1)
    p.write_text(text,encoding="utf-8")
    print("✅ installed")
