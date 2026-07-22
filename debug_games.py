FILE="handlers/message_handler.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

old='if clean_text.strip() == "لیست بازی":'

new='if "لیست بازی" in clean_text.strip():'

if old not in text:
    print("COMMAND NOT FOUND")
else:
    text=text.replace(old,new)

    with open(FILE,"w",encoding="utf-8") as f:
        f.write(text)

    print("GAME COMMAND DEBUG FIXED")
