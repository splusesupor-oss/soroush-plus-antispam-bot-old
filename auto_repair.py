import os,re

files=[
"handlers/message_handler.py",
"core/bot.py"
]

for f in files:
    if not os.path.exists(f):
        continue

    s=open(f,encoding="utf-8").read()

    # اصلاح self های باقی مانده در هندلر جدا شده
    if "handlers/message_handler.py" in f:
        s=s.replace('hasattr(self, "flood_messages")','hasattr(bot, "flood_messages")')
        s=s.replace('self.flood_messages','bot.flood_messages')
        s=s.replace('self.delete_notice_lock','bot.delete_notice_lock')
        s=s.replace('self.client','bot.client')
        s=s.replace('self.logger','bot.logger')

    # اضافه کردن import های جا افتاده
    if f=="handlers/message_handler.py":
        if "add_kick" not in s:
            s="from modules.admin_storage import add_kick\n"+s

    open(f,"w",encoding="utf-8").write(s)

print("AUTO REPAIR DONE")
