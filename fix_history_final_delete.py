from pathlib import Path

p=Path("handlers/message_handler.py")
t=p.read_text(encoding="utf-8")

# جلوگیری از چند بار اجرای HISTORY
old='''                print("🚨 HISTORY REPEAT BAN:", user_id)
'''

new='''                if getattr(bot, "_history_banned", None) == (chat_id, user_id):
                    return

                bot._history_banned = (chat_id, user_id)

                print("🚨 HISTORY REPEAT BAN:", user_id)
'''

t=t.replace(old,new)


# جایگزین حذف با نسخه مطمئن
start=t.find("                if ids:")
end=t.find("                print(f\"🚨 BAN FROM HISTORY", start)

if start!=-1 and end!=-1:
    block='''                if ids:
                    try:
                        print("🗑️ DELETING HISTORY:", len(ids))

                        for msg_id in ids:
                            try:
                                await bot.client.delete_messages(
                                    chat_id,
                                    msg_id
                                )
                            except:
                                pass

                    except Exception as err:
                        print("DELETE HISTORY ERROR:", err)

'''
    t=t[:start]+block+t[end:]
    print("✅ delete replaced")


p.write_text(t,encoding="utf-8")
print("DONE")
