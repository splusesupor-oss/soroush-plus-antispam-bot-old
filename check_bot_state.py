import os

print("=== MAIN IMPORT ===")
for f in ["main.py","core/bot.py"]:
    if os.path.exists(f):
        print("\nFILE:",f)
        with open(f,encoding="utf-8") as x:
            for i,l in enumerate(x,1):
                if "handle_new_message" in l or "message_handler" in l:
                    print(i,l.strip())

print("\n=== COMMANDS ===")
for root,dirs,files in os.walk("."):
    for file in files:
        if file.endswith(".py"):
            p=os.path.join(root,file)
            try:
                data=open(p,encoding="utf-8").read()
                for word in ["add_kick","اخراج","سکوت","ربات","help","mute","kick"]:
                    if word in data:
                        print(p,"=>",word)
            except:
                pass

print("\n=== HANDLERS ===")
for root,dirs,files in os.walk("handlers"):
    for file in files:
        if file.endswith(".py"):
            print(os.path.join(root,file))
