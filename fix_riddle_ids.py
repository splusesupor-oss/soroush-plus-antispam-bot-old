from pathlib import Path
import shutil

p = Path("main.py")
shutil.copy(p, "main.py.before_riddle_ids")

s = p.read_text(encoding="utf-8")

target = "            # RIDDLE_MOVED_BEFORE_FILTER\n"

insert = '''            # آماده سازی شناسه ها برای چیستان
            try:
                sender = await event.get_sender()
                user_id = getattr(sender, "id", 0)

                chat = await event.get_chat()
                chat_id = getattr(chat, "id", 0)
            except Exception:
                user_id = 0
                chat_id = 0

'''

if target not in s:
    print("target not found")
    exit()

s = s.replace(target, insert + target)

p.write_text(s, encoding="utf-8")
print("fixed")
