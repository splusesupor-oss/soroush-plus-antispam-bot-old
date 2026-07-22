FILE = "handlers/message_handler.py"

with open(FILE, "r", encoding="utf-8") as f:
    text = f.read()

backup = FILE + ".bak_add_game_list"

with open(backup, "w", encoding="utf-8") as f:
    f.write(text)

if 'if clean_text.strip() == "لیست بازی":' in text:
    print("GAME LIST ALREADY EXISTS")
    exit()

marker = '        # راهنمای ربات\n'

if marker not in text:
    print("MARKER NOT FOUND")
    exit()

block = '''        # لیست بازی
        if clean_text.strip() == "لیست بازی":
            games_text = (
                "🎮 لیست بازی ها:\\n\\n"
                "🧩 چیستان\\n"
                "یک چیستان با زمان کم دریافت کنید\\n\\n"
                "🎯 جرعت - حقیقت\\n"
                "یک سوال جرعت یا حقیقت تصادفی\\n\\n"
                "😂 جک\\n"
                "یک جک خنده دار دریافت کنید"
            )

            await event.reply(games_text)
            return

'''

text = text.replace(marker, block + marker, 1)

with open(FILE, "w", encoding="utf-8") as f:
    f.write(text)

print("GAME LIST ADDED")
print("BACKUP:", backup)
