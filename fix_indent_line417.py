FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

backup=FILE+".bak_indent417"

with open(backup,"w",encoding="utf-8") as f:
    f.write(text)

text=text.replace(
'await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")',
'                    await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")'
)

text=text.replace(
'                          return\n\n                      chat = await event.get_chat()',
'                    return\n\n            chat = await event.get_chat()'
)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("INDENT FIXED")
print("BACKUP:",backup)
