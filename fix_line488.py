FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

old='                                            await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")'

new='                        await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")'

text=text.replace(old,new)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("LINE 488 FIXED")
