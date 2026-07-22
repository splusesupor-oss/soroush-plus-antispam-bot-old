from pathlib import Path

old=Path("handlers/message_handler.py")
backup=Path("handlers/message_handler.py.SAFE_NOW")

a=old.read_text(encoding="utf-8")
b=backup.read_text(encoding="utf-8")

checks=[
"search_web",
"can_search",
"spam_history",
"is_repeat",
"HISTORY REPEAT BAN",
"new_fill",
"get_jorat",
"get_haghighat",
"MessageEntityBold",
"add_mute",
"اخطار",
"صفر کردن تخلفات"
]

print("🔎 CHECK")

for x in checks:
    print(("✅" if x in a else "❌"),x)

