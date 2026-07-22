p="handlers/message_handler.py"

data=open(p,encoding="utf-8").read()

old="from modules.group_stats import add_message"

new="from modules.group_stats import add_message, add_kick, add_mute"

if old in data:
    data=data.replace(old,new)
    open(p,"w",encoding="utf-8").write(data)
    print("FIXED import")
else:
    print("import line not found")
