import ast

files = [
    "handlers/message_handler.py",
    "core/bot.py"
]

fixes = {
    "add_kick": "from modules.group_stats import add_kick",
    "add_mute": "from modules.group_stats import add_mute",
    "add_message": "from modules.group_stats import add_message",
    "MessageEntityBold": "from splusthon.tl.types import MessageEntityBold",
    "MessageEntityBlockquote": "from splusthon.tl.types import MessageEntityBlockquote",
    "new_riddle": "from modules.riddles import new_riddle, get_answer",
}

for file in files:
    try:
        data=open(file,encoding="utf8").read()
    except:
        continue

    try:
        tree=ast.parse(data)
    except:
        continue

    names=set()

    for node in ast.walk(tree):
        if isinstance(node,ast.Name):
            names.add(node.id)

    imports=data.split("\n")

    add=[]

    for name,imp in fixes.items():
        if name in names and imp not in data:
            add.append(imp)

    if add:
        data="\n".join(add)+"\n"+data
        open(file,"w",encoding="utf8").write(data)
        print("FIXED:",file,add)
    else:
        print("OK:",file)

