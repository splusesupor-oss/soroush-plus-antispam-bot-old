p="main.py"

s=open(p,encoding="utf-8").read()

old='''if clean_text in auto_replies:
                await event.reply(auto_replies[clean_text])
                return'''

new='''for key, reply in auto_replies.items():
                if key in clean_text:
                    await event.reply(reply)
                    return'''

if old in s:
    s=s.replace(old,new)
    open(p,"w",encoding="utf-8").write(s)
    print("✅ پاسخ‌های داخل جمله فعال شد")
else:
    print("❌ بخش پیدا نشد")
