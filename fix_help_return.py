FILE="test_main.py"

with open(FILE,"r",encoding="utf-8") as f:
    text=f.read()

backup=FILE+".bak_fix_help_return"

with open(backup,"w",encoding="utf-8") as f:
    f.write(text)

old='''                  )
                      await event.reply("❌ فقط مالک ربات اجازه این دستور را دارد")
                          return

                      chat = await event.get_chat()
                      gid = getattr(chat, "id", None)
                      title = getattr(chat, "title", )

                      if clean_text == "فعال سازی":
                          activate_group(gid, title)
                          await event.reply(
                              f"🦊 روباه در گروه «{title}» فعال سازی شد ✅"
                          )

                      else:
                          deactivate_group(gid, title)
                          await event.reply(
                              f"🦊 روباه در گروه «{title}» غیر فعال شد ❌"
                          )

                  except Exception as e:
                      await event.reply(f"❌ خطا: {e}")

                  return
'''

new='''                  )
                  await event.reply(help_text)
                  return
'''

if old not in text:
    print("BLOCK NOT FOUND")
    exit()

text=text.replace(old,new)

with open(FILE,"w",encoding="utf-8") as f:
    f.write(text)

print("HELP RETURN FIXED")
print("BACKUP:",backup)
