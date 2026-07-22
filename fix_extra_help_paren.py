FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

backup=FILE+".bak_extra_help_paren"

with open(backup,"w",encoding="utf-8") as f:
    f.write(text)

old='''                    "@osine1"
                )


                    )
                    await event.reply(help_text)'''

new='''                    "@osine1"
                )

                await event.reply(help_text)'''

if old not in text:
    print("PATTERN NOT FOUND")
    exit()

text=text.replace(old,new)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("EXTRA HELP PAREN FIXED")
print("BACKUP:",backup)
