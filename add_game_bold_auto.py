FILE = "handlers/message_handler.py"

with open(FILE, "r", encoding="utf-8") as f:
    text = f.read()

backup = FILE + ".bak_game_bold"

with open(backup, "w", encoding="utf-8") as f:
    f.write(text)

target = '"🧩 چیستان",'

if target not in text:
    print("BOLD LIST NOT FOUND")
    exit()

add = '''"🧩 چیستان",
                    "🎯 جرعت - حقیقت",
                    "😂 جک:",
                    "✍️ جای خالی",'''

text = text.replace(target, add, 1)

with open(FILE, "w", encoding="utf-8") as f:
    f.write(text)

print("GAME BOLD ADDED")
print("BACKUP:", backup)
