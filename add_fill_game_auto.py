FILE = "handlers/message_handler.py"

with open(FILE, "r", encoding="utf-8") as f:
    text = f.read()

backup = FILE + ".bak_add_fill_game"

with open(backup, "w", encoding="utf-8") as f:
    f.write(text)

old = '''"😂 جک\\n"
                "یک جک خنده دار دریافت کنید"'''

new = '''"😂 جک\\n"
                "یک جک خنده دار دریافت کنید\\n\\n"
                "✍️ جای خالی\\n"
                "۳۰ ثانیه فرصت دارید جای خالی را کامل کنید"'''

if old not in text:
    print("GAME TEXT PATTERN NOT FOUND")
    exit()

text = text.replace(old, new, 1)

with open(FILE, "w", encoding="utf-8") as f:
    f.write(text)

print("FILL GAME ADDED")
print("BACKUP:", backup)
