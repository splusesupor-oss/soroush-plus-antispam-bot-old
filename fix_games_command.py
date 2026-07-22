FILE="handlers/message_handler.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

backup=FILE+".bak_games"

with open(backup,"w",encoding="utf-8") as f:
    f.write(text)

old='if clean_text.strip() == "لیست بازی":'

new='if clean_text.strip() in ["لیست بازی", "لیست بازی ها", "لیست بازی‌ها", "بازی ها", "بازی‌ها"]:'

if old not in text:
    print("NOT FOUND")
    exit()

text=text.replace(old,new)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("GAMES COMMAND FIXED")
print("BACKUP:",backup)
