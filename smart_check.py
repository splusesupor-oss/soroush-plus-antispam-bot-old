import os,ast

print("🔎 CHECK START")

for root,dirs,files in os.walk("."):
    if "__pycache__" in root:
        continue

    for file in files:
        if not file.endswith(".py"):
            continue

        path=os.path.join(root,file)

        try:
            data=open(path,encoding="utf-8").read()
        except:
            continue

        try:
            ast.parse(data)
        except Exception as e:
            print("\n❌ SYNTAX ERROR")
            print(path)
            print(e)

        for word in [
            "kick_participant",
            "edit_permissions",
            "add_banned",
            "remove_banned",
            "is_banned",
            "ChatAction",
            "NewMessage"
        ]:
            if word in data:
                print("✅",word,"->",path)

print("\n🏁 DONE")
